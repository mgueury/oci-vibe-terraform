DATE_POSTFIX=`date '+%Y%m%d-%H%M%S'`
MIGRATION_DIR="$HOME/migration/$DATE_POSTFIX"

create_documentation()
{
  cline -y > /tmp/cline_cli.log << EOF
You are a senior software engineer and technical writer.

Goal:
Analyze the provided source code of an application and generate comprehensive, structured technical documentation suitable for engineers who need to understand, maintain, or migrate the system.

Input:
- Source code. Check the current directory.

Tasks:

1. System Overview
   - Describe the purpose of the application
   - Identify main use cases
   - High-level architecture (monolith, microservices, layers, etc.)

2. Architecture & Components
   - Identify main modules/components/services
   - Explain responsibilities of each component
   - Describe how components interact (data flow, APIs, events)

3. Key Features
   - Extract and describe all functional features
   - Group them by domain (e.g., authentication, data processing, reporting, etc.)

4. APIs & Interfaces
   - List exposed APIs (REST, GraphQL, RPC, etc.)
   - Describe endpoints, inputs, outputs, and behavior
   - Include important data models and schemas

5. Data Model
   - Identify main entities, relationships, and schemas
   - Describe persistence layer (DB type, ORM, key tables/collections)

6. Workflows & Business Logic
   - Describe key flows (e.g., user login, transaction processing)
   - Highlight important algorithms or logic

7. Configuration & Dependencies
   - List external dependencies (services, APIs, libraries)
   - Describe configuration (env variables, config files)

8. Security & Constraints
   - Authentication/authorization mechanisms
   - Data validation and error handling
   - Any security-sensitive areas

9. Non-Functional Aspects (if inferable)
   - Performance considerations
   - Scalability patterns
   - Logging/monitoring

10. Gaps & Uncertainties
   - Clearly state assumptions
   - Highlight unclear or undocumented parts of the code

Output Files:
- User Manual: USER.md
- Technical Manual: TECH.md

Output format:
- Well-structured documentation with clear sections
- Use diagrams in text form where helpful (e.g., component interactions)
- Be precise and avoid guessing—flag uncertainties explicitly
EOF
}

cd $HOME/migration/app_to_migrate
create_documentation
mkdir -p $MIGRATION_DIR/app_to_migrate
mv /tmp/cline_cli.log $MIGRATION_DIR/cline_cli_app_to_migrate.log
cp $HOME/migration/app_to_migrate/*.md $MIGRATION_DIR/app_to_migrate

cd $HOME/app
create_documentation
mkdir -p $MIGRATION_DIR/app_target
mv /tmp/cline_cli.log $MIGRATION_DIR/cline_cli_app_target.log
cp $HOME/app/*.md $MIGRATION_DIR/app_target

cd $MIGRATION_DIR
cline -y << EOF
You are a senior software architect and product analyst.

Goal:
Compare the functionality of two applications (app_to_migrate and app_target) based on their documentation and produce a detailed gap analysis to support a migration from app_to_migrate to app_target.

Inputs:
- app_to_migrate documentation: app_to_migrate/*.md
- app_target documentation: app_target/*.md

Tasks:
1. Extract and list all features of app_to_migrate, grouped by functional domains (e.g., authentication, reporting, APIs, UI, integrations, performance, security, etc.).
2. Extract and list all features of app_target using the same structure.
3. Create a comparison table with:
   - Feature name
   - Description
   - Present in app_to_migrate (yes/no)
   - Present in app_target (yes/no/partial)
   - Gap type (missing / partial / equivalent / different implementation)
4. Identify:
   - Features present in app_to_migrate but missing or incomplete in app_target
   - Features in app_target that could replace app_to_migrate features (even if implemented differently)
5. For each gap:
   - Describe the gap clearly
   - Assess migration impact (low / medium / high)
   - Suggest possible solutions (configuration, customization, workaround, or development)
6. Highlight:
   - Critical blockers for migration
   - Risks and dependencies
   - Assumptions made due to missing or unclear documentation

Output File:
- gap_analysis.md

Output format:
- Executive summary
- Feature comparison table
- Detailed gap analysis
- Migration risk assessment
- Recommendations and next steps

Be precise, avoid speculation, and clearly state uncertainties.
EOF

echo
cat $MIGRATION_DIR/gap_analysis.md
echo
echo "Output is in file: $MIGRATION_DIR/gap_analysis.md"
