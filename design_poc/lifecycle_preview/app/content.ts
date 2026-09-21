export const stages=['Screening','Panel Review','Recruiter Phone Call','Assignment','Discussion 1','Discussion 2','Discussion 3','Reference Check','Offer Stage','Joined','CV Reject','Interview Reject','Drop Out','On Hold','Offer Drop out'];
export const candidates=[{name:'Maya Chen',role:'Product Designer',stage:'Panel Review',source:'LinkedIn',country:'Singapore',initials:'MC',note:'Panel feedback ready',days:2},{name:'Arjun Mehta',role:'Data Engineer',stage:'Reference Check',source:'Referral',country:'India',initials:'AM',note:'References verified',days:1},{name:'Linh Nguyen',role:'Senior Agronomist',stage:'Discussion 1',source:'Careers page',country:'Vietnam',initials:'LN',note:'Interview tomorrow',days:3},{name:'Dewi Putri',role:'Field Operations Lead',stage:'Screening',source:'Agency',country:'Indonesia',initials:'DP',note:'Review application',days:1},{name:'Sofia Tan',role:'Product Designer',stage:'On Hold',source:'LinkedIn',country:'Singapore',initials:'ST',note:'Update promised 25 Sep',days:5},{name:'Ravi Shah',role:'Data Engineer',stage:'Offer Stage',source:'Referral',country:'India',initials:'RS',note:'Salary review needed',days:2}];
export const roles=[{name:'Product Designer',country:'Singapore',team:'Product',state:'Open for candidates',count:3,budget:'SGD 96,000',owner:'Alex Morgan'},{name:'Senior Agronomist',country:'Vietnam',team:'Agronomy',state:'Awaiting approval',count:1,budget:'VND 600,000,000',owner:'Sam Lee'},{name:'Data Engineer',country:'India',team:'Engineering',state:'Open for candidates',count:2,budget:'INR 2,400,000',owner:'Alex Morgan'},{name:'Field Operations Lead',country:'Indonesia',team:'Operations',state:'JD in review',count:1,budget:'IDR 360,000,000',owner:'Sam Lee'}];
export const emails=[
{name:'Application received',trigger:'Application submitted',subject:"We got your application - here's what happens next",body:`Hi {{first_name}},

Thanks for applying for the {{role}} role at {{brand}}. Your application landed with us, and a real person (not a black hole) will be reading it.

We take about two weeks to go through applications properly, so you'll hear from us within that time either way. If two weeks pass and you haven't, feel free to nudge us.

{{company_intro}}

Talk soon.
Talent Team
{{website}} | {{linkedin}}`},
{name:"Let's chat",trigger:'Recruiter Phone Call',subject:"Let's chat — {{role}} at {{brand}}",body:`Hi {{first_name}},

Good news - we liked what we saw, and we'd love to get to know you a bit better.

The next step is a relaxed conversation with {{hr_name}} from our team. Nothing to prepare, no trick questions. It's really just a chance for us to hear about you and what you're after, and for you to ask us anything - the role, the team, what we're building, all of it.

It'll take about {{duration}} minutes. Grab a time that works for you here: {{scheduling_link}}.

Looking forward to it,
{{sender_name}}
{{website}} | {{linkedin}}`},
{name:'Assignment',trigger:'Assignment',subject:'A short assignment for the {{role}} role',body:`Hi {{first_name}},

Thanks for a great conversation. The next step is a short assignment - it gives you a feel for the kind of problems we work on, and gives us a sense of how you think.

Here's what we'd like you to cover:
{{tasks}}
{{format}}

We're not after hours of polish or a flawless finish. We care far more about your thinking than a perfect wrapper.

Please send it over by {{deadline}}. If life gets in the way and you need more time, just tell us - we'd rather you do your best work than rush it.

Send your submission to {{submission_link}}, and if anything's unclear, reply here.

Good luck,
{{sender_name}}
{{website}} | {{linkedin}}`},
{name:'On hold / delay',trigger:'On Hold',subject:'A quick, honest update on your application',body:`Hi {{first_name}},

I wanted to reach out rather than leave you wondering. We're still working through our decision on the {{role}} role, and it's taking a bit longer than we'd hoped — {{reason}}.

I don't want to rush a decision that matters, and I also don't want to leave you in the dark. Where things stand: we're keeping your application very much active, and I expect to have a clearer update for you by {{update_date}}.

If your situation changes in the meantime — another offer, a shift in timing — please tell me. I'll do my best to move things along on our end so you're not left waiting unfairly.

Thanks for your patience, and sorry for the wait.

Best,
{{sender_name}}
{{brand}}`},
{name:'Application not progressing',trigger:'CV Reject',subject:'Your application to {{brand}}',body:`Hi {{first_name}},

Thanks for taking the time to apply for the {{role}} role, and for your interest in what we're building at {{brand}}.

After going through your application, we've decided not to take it forward this time. These calls are rarely black and white, and this one isn't a knock on your ability — it usually comes down to how closely the experience lines up with what this particular role needs right now.

We'd genuinely welcome you to apply again for roles that fit down the line. Thank you once again for your interest, and we wish you every success ahead.

Warmly,
{{sender_name}}`}
];
export const jdSections=[['About Rize',`At Rize, we are building the digital infrastructure powering the future of sustainable rice cultivation across Southeast Asia.

Rice farming supports the livelihoods of millions of smallholder farmers, yet it is also one of the world's largest contributors to methane emissions, accounting for nearly 12% of global methane emissions and close to 30% across Southeast Asia. The transition toward modern, measurable, and lower-emission farming is no longer optional. It is inevitable.

Rize exists to accelerate that transition.

Founded through a joint venture between Temasek, Wavemaker Impact, Breakthrough Energy Ventures, and GenZero, Rize combines climate technology, agricultural intelligence, and last-mile operational infrastructure to help make rice cultivation more productive, resilient, and sustainable.`],['What We Are Building',`We are building a technology platform that enables large-scale sustainable rice farming through:
• Field operations and task management
• Cultivation and farm activity tracking across millions of hectares of paddy fields
• Agricultural data capture and verification
• Agri-input supply chain management
• Access to financing and third-party agricultural services
• Climate and sustainability reporting infrastructure

This ecosystem helps farmers become more climate-resilient, improve yields, reduce farming costs, and adopt modern agricultural practices with measurable impact.`],['Our Mission',`Decarbonise rice agriculture: Eliminate 100 megatons of carbon emissions by 2040
Improve farmer livelihoods: Increase yields, reduce cost-to-farm, and improve access to financing
Build trusted agricultural infrastructure: Create a scalable and verifiable platform for sustainable farming practices`],['Where We Operate',`Vietnam (Mekong Delta region)
Indonesia (Java Island and expansion regions)`],['Why Join Rize',`At Rize, you will work on problems that sit at the intersection of climate, agriculture, technology, and livelihoods. Our work directly impacts farmers, food systems, and sustainability outcomes across the region.

We are building with urgency, ownership, and long-term impact in mind.

You can learn more about us here:
www.rize.farm
Rize LinkedIn`]];
