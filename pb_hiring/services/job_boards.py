"""Documented provider contracts. No credentials, network calls or business decisions."""

import hashlib
import hmac
import re
from urllib.parse import urlsplit

LINKEDIN_VERSION = "202604"
BOARD_PROVIDERS = {"linkedin": "linkedin", "jobstreet": "seek"}


def signed(provider, secret, raw, signature):
    if not secret or not isinstance(signature, str):
        return False
    if provider == "seek":
        expected = hmac.new(secret.encode(), raw, hashlib.sha512).hexdigest()
    else:
        expected = (
            "hmacsha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        )
    return hmac.compare_digest(expected, signature)


def media_url(provider, url):
    p = urlsplit(url)
    host = "www.linkedin.com" if provider == "linkedin" else "graphql.seek.com"
    if (
        p.scheme != "https"
        or p.hostname != host
        or p.port not in (None, 443)
        or p.username
        or p.password
        or p.fragment
    ):
        raise ValueError("Unexpected document download address")
    if provider == "linkedin" and not p.path.startswith("/ambry/"):
        raise ValueError("Unexpected document download path")
    return url


def linkedin_application(data):
    if data.get("type") != "EXPORT_JOB_APPLICATION":
        raise ValueError("Unsupported application event")
    q = data.get("questionResponses") or {}
    contact = q.get("contactInformationQuestionResponses") or {}
    answer = lambda key: str((contact.get(key) or {}).get("value") or "").strip()
    result = {
        "external_id": str(data.get("jobApplicationId") or ""),
        "job_id": str(data.get("externalJobId") or ""),
        "name": " ".join(
            filter(None, [answer("firstNameAnswer"), answer("lastNameAnswer")])
        ),
        "email": answer("emailAnswer"),
        "phone": answer("cellphoneNumberQuestionAnswer"),
        "resume_url": str(
            (
                (q.get("resumeQuestionResponses") or {}).get("resumeQuestionAnswer")
                or {}
            ).get("mediaUrl")
            or ""
        ),
    }
    if (
        not result["external_id"]
        or not result["job_id"]
        or not result["name"]
        or not result["email"]
    ):
        raise ValueError("Incomplete application")
    return result


def linkedin_job(values, cfg, reference, callback, operation="CREATE"):
    if not re.fullmatch(r"urn:li:organization:\d+", cfg.get("organization_id", "")):
        raise ValueError("Enter the provider-approved organization identifier")
    body = {
        "externalJobPostingId": reference,
        "integrationContext": cfg["organization_id"],
        "jobPostingOperationType": operation,
    }
    if operation != "CLOSE":
        body.update(
            title=values["title"],
            description=values["description"],
            location=values["location"],
            listedAt=values["listed_at"],
            companyApplyUrl=values["apply_url"],
            availability="PUBLIC",
            listingType="BASIC",
        )
        if values.get("native_apply"):
            body["onsiteApplyConfiguration"] = {
                "jobApplicationWebhookUrl": callback,
                "questions": {
                    "contactInformationQuestions": {},
                    "resumeQuestions": {"resumeQuestionRequirement": "REQUIRED"},
                },
            }
    return {"elements": [body]}


def seek_profile(values, cfg, reference, idempotency):
    for key in ("hirer_id", "contact_name", "contact_email"):
        if not cfg.get(key):
            raise ValueError("Complete the hiring organization and contact settings")
    for key in (
        "location_id",
        "category_id",
        "product_id",
        "currency",
        "pay_interval",
        "work_type",
    ):
        if not values.get(key):
            raise ValueError(
                "Complete location, category, ad product, salary and work type"
            )
    if values["pay_interval"] not in ("Hour", "Month", "Year"):
        raise ValueError("Unsupported salary interval")
    minimum, maximum = values["salary_min"], values["salary_max"]
    if minimum <= 0 or maximum < minimum:
        raise ValueError("Enter a valid salary range")
    instruction = {
        "idempotencyId": idempotency,
        "seekAdvertisementProductId": values["product_id"],
    }
    # Omitting applicationMethods selects the provider-hosted application form.
    if not values.get("native_apply"):
        instruction["applicationMethods"] = [
            {"applicationUri": {"url": values["apply_url"]}}
        ]
    profile = {
        "positionTitle": values["title"],
        "positionOrganizations": [cfg["hirer_id"]],
        "positionLocation": [values["location_id"]],
        "jobCategories": [values["category_id"]],
        "positionFormattedDescriptions": [
            {"descriptionId": "AdvertisementDetails", "content": values["description"]},
            {"descriptionId": "SearchSummary", "content": values["summary"]},
        ],
        "offeredRemunerationPackage": {
            "basisCode": "Hourly" if values["pay_interval"] == "Hour" else "Salaried",
            "descriptions": [],
            "ranges": [
                {
                    "intervalCode": values["pay_interval"],
                    "minimumAmount": {"currency": values["currency"], "value": minimum},
                    "maximumAmount": {"currency": values["currency"], "value": maximum},
                }
            ],
        },
        "seekAnzWorkTypeCode": values["work_type"],
        "seekWorkArrangementCodes": [values["arrangement"]],
        "seekHirerJobReference": reference,
        "seekPartnerMetadata": reference,
        "postingInstructions": [instruction],
    }
    opening = {
        "postingRequester": {
            "id": cfg["hirer_id"],
            "roleCode": "Company",
            "personContacts": [
                {
                    "name": {"formattedName": cfg["contact_name"]},
                    "roleCode": "PositionContact",
                    "communication": {
                        "email": [{"address": cfg["contact_email"]}],
                        "phone": [],
                    },
                }
            ],
        },
        "seekPartnerMetadata": reference,
    }
    return {"positionOpening": opening, "positionProfile": profile}


SEEK_CHECK = "query($id:String!){hiringOrganization(id:$id){id{value} name}}"
SEEK_POST = """mutation($input:PostPositionInput!){postPosition(input:$input){__typename
 ... on PostPositionPayload_Success{positionProfile{profileId{value}}}
 ... on PostPositionPayload_Conflict{conflictingPositionProfile{profileId{value}}}}}"""
SEEK_UPDATE = """mutation($input:UpdatePostedPositionProfileInput!){updatePostedPositionProfile(input:$input){__typename}}"""
SEEK_CLOSE = """mutation($input:ClosePostedPositionProfileInput!){closePostedPositionProfile(input:$input){__typename}}"""
SEEK_STATUS = """query($id:String!){positionProfile(id:$id){profileId{value} positionUri
 positionOrganizations{id{value}} ... on PostedPositionProfile{seekStatusCode}}}"""
SEEK_APPLICATION = """query($id:String!){candidateProfile(id:$id){profileId{value}
 associatedPositionProfile{profileId{value} positionOrganizations{id{value}}}
 candidate{person{name{formattedName} communication{email{address} phone{formattedNumber}}}}
 attachments{url seekRoleCode}}}"""


def seek_application(profile, hirer):
    job = profile.get("associatedPositionProfile") or {}
    if hirer not in [
        (x.get("id") or {}).get("value") for x in job.get("positionOrganizations", [])
    ]:
        raise ValueError("Application belongs to a different hiring organization")
    person = (profile.get("candidate") or {}).get("person") or {}
    communication = person.get("communication") or {}
    emails, phones = communication.get("email") or [], communication.get("phone") or []
    result = {
        "external_id": (profile.get("profileId") or {}).get("value", ""),
        "job_id": (job.get("profileId") or {}).get("value", ""),
        "name": (person.get("name") or {}).get("formattedName", ""),
        "email": emails[0].get("address", "") if emails else "",
        "phone": phones[0].get("formattedNumber", "") if phones else "",
        "resume_url": next(
            (
                a.get("url", "")
                for a in profile.get("attachments", [])
                if a.get("seekRoleCode") == "Resume"
            ),
            "",
        ),
    }
    if not all(result[k] for k in ("external_id", "job_id", "name", "email")):
        raise ValueError("Incomplete application")
    return result
