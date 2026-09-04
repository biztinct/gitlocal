# AI-Enabled Employee Development System

A comprehensive, AI-native employee development platform for Odoo 19 CE.

## Features

### 1. AI-Driven Talent Intelligence
- **Multi-source skills inference**: Automatically detect skills from project tasks, course completions, and assessments
- **AI-powered recommendations**: Course suggestions, mentor matching, career path guidance
- **Skills gap analysis**: Compare employee skills against job requirements

### 2. Learning Experience Platform (LXP)
- **Personalized learning paths**: AI-curated course sequences based on skill gaps
- **Integration with website_slides**: Leverages Odoo's built-in eLearning platform
- **Progress tracking**: Real-time monitoring of learning progress and completion

### 3. Continuous Performance & Coaching
- **AI coaching nudges**: Real-time suggestions based on KPIs, deadlines, and performance
- **Coaching sessions**: Track 1-on-1 coaching interactions
- **Performance feedback**: Sentiment analysis and actionable insights

### 4. Mentoring, Career & Internal Mobility
- **AI mentorship matching**: Intelligent pairing based on skills, goals, and compatibility
- **Career path templates**: Define progression routes with skill evolution
- **Development plans**: SMART objectives linked to learning and skills

### 5. Skills & Capability Framework
- **Comprehensive skills taxonomy**: Technical, soft skills, domain knowledge, certifications
- **Proficiency tracking**: 5-level system (Beginner → Expert)
- **Peer endorsements**: Social validation of skills
- **Multi-source aggregation**: Weighted scores from AI, managers, peers, self, and courses

### 6. Knowledge & Organizational Memory
- **Knowledge graph**: Link knowledge to projects, outcomes, and expertise
- **AI knowledge extraction**: Automatically capture lessons learned from completed projects
- **Expert finder**: Discover who knows what in your organization

### 7. Employee Experience & Engagement
- **Self-service dashboards**: Employees view skills, courses, and development plans
- **Manager dashboards**: Team skills heat maps and gap analysis
- **Gamification**: Badges and achievements for skill milestones

### 8. Analytics, Governance & Ecosystem Integration
- **Development analytics**: Training ROI, completion rates, skill coverage
- **Role-based access**: User, Manager, and Administrator roles
- **Audit trails**: Track skill changes and assessments

## AI Provider Support

The system supports multiple AI providers, switchable via configuration:

- **Llama/Ollama** (default, open-source): Self-hosted via Ollama
- **Mistral** (open-source): Self-hosted
- **OpenAI ChatGPT** (optional): API-based, requires API key
- **Odoo 19 Native AI**: Built-in fallback with rule-based logic

## Installation

1. Copy the module to your Odoo addons directory
2. Update the app list: `Settings → Apps → Update Apps List`
3. Install: Search for "AI-Enabled Employee Development System"

## Configuration

### AI Provider Setup

1. Go to `Employee Development → Configuration → AI Provider`
2. Select your preferred provider:
   - **Odoo Native**: No setup required (default)
   - **Llama/Ollama**: Install Ollama locally, configure endpoint
   - **OpenAI**: Add your API key
3. Test the connection

### Initial Setup

1. **Skills Taxonomy**: Review and customize skill categories and skills
2. **Skill Levels**: Adjust proficiency level definitions if needed
3. **Job Skills**: Define required skills for each job position
4. **Learning Paths**: Create learning paths linking courses to skills

## Usage

### For Employees

1. **View Your Skills**: Navigate to your employee profile to see your skills
2. **Self-Assessment**: Use the Skill Assessment wizard to evaluate your skills
3. **AI Skills Inference**: Click "Infer Skills from Work" to auto-detect skills from your tasks
4. **Learning**: Browse recommended courses based on your skill gaps
5. **AI Coaching**: Access AI coaching chat for personalized guidance
6. **Development Plan**: Create and track your development objectives

### For Managers

1. **Team Skills Overview**: View your team's collective skills and gaps
2. **Skill Gap Analysis**: Identify team training needs
3. **Development Plans**: Create and review employee development plans
4. **Coaching Sessions**: Document coaching conversations
5. **Mentorship**: Match team members with mentors

### For Administrators

1. **Skills Management**: Maintain the skills taxonomy
2. **Learning Path Curation**: Create structured learning journeys
3. **Career Paths**: Define career progression templates
4. **Knowledge Extraction**: Run automated knowledge extraction from projects
5. **Analytics**: Monitor development metrics and ROI

## Technical Architecture

### Models

**Skills Framework:**
- `hr.skill.category`: Skill groupings
- `hr.skill`: Skills library
- `hr.skill.level`: Proficiency levels
- `hr.employee.skill`: Employee ↔ Skills with multi-source scores
- `hr.job.skill`: Job requirements
- `hr.skill.gap`: Gap analysis with AI recommendations

**Learning & Development:**
- `hr.learning.path`: Structured learning journeys
- `hr.learning.enrollment`: Employee enrollments
- `hr.certification`: Certifications with expiry tracking
- `hr.development.plan`: Individual development plans
- `hr.development.objective`: SMART objectives

**Coaching & Mentoring:**
- `hr.coaching.session`: Coaching interactions
- `hr.coaching.nudge`: AI-generated suggestions
- `hr.mentorship`: Mentor-mentee relationships
- `hr.mentorship.session`: Mentorship meetings

**Career & Knowledge:**
- `hr.career.path`: Career progression templates
- `hr.knowledge.node`: Knowledge graph nodes
- `hr.knowledge.edge`: Knowledge relationships

### AI Integration

The module uses an abstraction layer (`ai_providers/`) supporting multiple AI backends:
- Base provider interface defining standard methods
- Provider factory for automatic instantiation
- Graceful fallback to Odoo Native when external AI unavailable

### Skills Inference Engine

Multi-method skills detection:
- **Project tasks**: AI text analysis of task descriptions
- **Course completions**: Automatic skill mapping
- **Self-assessments**: Employee input
- **Manager assessments**: Manager reviews
- **Peer endorsements**: Social validation
- **Weighted aggregation**: Combines all sources with configurable weights

## Dependencies

- Odoo 19 Community Edition
- Standard modules: `hr`, `website_slides`, `gamification`, `project`, `mail`
- Optional: `hr_timesheet` for enhanced skills tracking
- Python packages: `requests` (for external AI providers)
- Optional: `openai` library (if using OpenAI provider)

## Roadmap

**Future Enhancements:**
- 360-degree feedback system
- Succession planning module
- External learning integration (Udemy, Coursera)
- Advanced analytics dashboards with predictive insights
- Mobile app for coaching and learning

## Support

For issues, questions, or feature requests, please contact your system administrator.

## License

LGPL-3

## Credits

Inspired by world-class platforms: SAP SuccessFactors, Workday Skills Cloud, BetterUp, Degreed, and Microsoft Viva.

