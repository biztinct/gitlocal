"""Provider-documented outbound feeds; never include candidate or account data."""
from lxml import etree


def render_feed(provider, jobs):
    if provider not in ('careerjet', 'jooble'):
        raise ValueError('Unsupported feed')
    root = etree.Element('jobs')
    for job in jobs:
        node = etree.SubElement(root, 'job', **({'id': job['id']} if provider == 'jooble' else {}))

        def put(parent, key, value):
            # Older server lxml rejects CDATA terminators; split them losslessly.
            content = str(value or '').replace(']]>', ']]]]><![CDATA[>')
            element = etree.fromstring(
                ('<' + key + '><![CDATA[' + content + ']]></' + key + '>').encode('utf-8'),
                parser=etree.XMLParser(strip_cdata=False, resolve_entities=False))
            parent.append(element)

        if provider == 'careerjet':
            put(node, 'id', job['id'])
            put(node, 'title', job['title'])
            put(node, 'url', job['url'])
            location = etree.SubElement(node, 'location')
            put(location, 'city', job['city'])
            put(location, 'country', job['country'])
            put(node, 'apply_url', job['apply_url'])
        else:
            put(node, 'name', job['title'])
            put(node, 'link', job['url'])
            put(node, 'region', ', '.join(filter(None, [job['city'], job['country']])) )
            put(node, 'pubdate', job['published'].strftime('%d.%m.%Y'))
            put(node, 'updated', job['updated'].strftime('%d.%m.%Y'))
            put(node, 'expire', job['expires'].strftime('%d.%m.%Y'))
        put(node, 'company', job['company'])
        put(node, 'description', job['description'])
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True)
