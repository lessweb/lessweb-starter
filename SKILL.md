---
name: lessweb-starter
description: Create new Lessweb projects from the example template. Use when the user wants to start a new Lessweb project, scaffold a Lessweb application, or create a project based on the Lessweb framework example.
---

# Lessweb Starter

Create a new Lessweb project based on the example template in the lessweb repository. This skill guides you through collecting project information and generating a complete project structure with all files properly configured.

## When to Use

Use this skill when:
- User wants to create a new Lessweb project
- User mentions "new project", "start a project", "scaffold", or "initialize" with Lessweb
- User wants to use the Lessweb framework example as a template

## Instructions

Follow these steps in order:

### Step 1: Collect Project Code Name

1. Ask the user for a project code name (e.g., "Moon Cake", "User Management System")

2. If the project code name is in Chinese:
   - Translate it to English
   - Show the translation to the user
   - Ask: "I've translated your project name to '{translated_name}'. Is this acceptable?"
   - Wait for confirmation before proceeding
   - If not acceptable, ask the user to provide their preferred English name

3. If already in English, use it directly

### Step 2: Validate Project Code Name

1. Check if the project code name ends with words like:
   - "API"
   - "Backend"
   - "Service"
   - "Server"
   - "Application"
   - "App"

2. If it does, remove the suffix and inform the user:
   - Example: "Moon Cake API" → "Moon Cake"
   - Say: "I've removed '{suffix}' from the project name. The project code will be '{cleaned_name}'."

3. The final project code name should be a simple, descriptive name without technical suffixes

### Step 3: Collect Project Description

1. Ask the user for a project description
   - Explain: "This description will be used in pyproject.toml and openapi.json"
   - If user doesn't provide one, suggest a default based on the project name:
     - Format: "{Project Name} - A SaaS application built with lessweb framework"

2. Store this description for later use

### Step 4: Determine Target Directory

1. Ask the user where to create the new project:
   - "Where would you like to create the new project? (provide full path, or '.' for current directory)"

2. Validate the target directory exists or can be created

### Step 5: Convert Project Names to Required Formats

Based on the project code name (e.g., "Moon Cake"), generate:

1. **Title Case** (for titles): "Moon Cake"
2. **Kebab Case** (for package name, filenames): "moon-cake"
3. **Snake Case** (for Python logger name): "moon_cake"

### Step 6: Copy and Transform Project Files

Copy all files from the `template/` directory (located in the same directory as this SKILL.md file) to the target directory, making the following replacements:

**Template Location**: The template directory is at `~/.agents/skills/lessweb-starter/template/` (or relative to this SKILL.md: `./template/`)

#### Files to Copy and Transform

Copy all files from the example directory structure:

```
example/
├── .env
├── .env.testci
├── .env.staging
├── .env.production
├── .gitignore
├── .gitlab-ci.yml
├── .pyway.conf
├── Dockerfile
├── Makefile
├── README.md
├── main.py
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── bullmq.toml
│   ├── jwt_gateway.toml
│   ├── lessweb.toml
│   ├── mysql.toml
│   ├── redis.toml
│   └── redis.production.toml
├── migration/
│   └── V01_01_01__init_tables.sql
├── openapi/
│   └── openapi.json
├── shared/
│   ├── __init__.py
│   ├── bullmq_plugin.py
│   ├── error_middleware.py
│   ├── jwt_gateway.py
│   ├── lessweb_commondao.py
│   └── redis_plugin.py
├── src/
│   ├── __init__.py
│   ├── controller/
│   │   ├── __init__.py
│   │   └── admin_controller.py
│   ├── entity/
│   │   ├── __init__.py
│   │   └── admin.py
│   ├── processor/
│   │   ├── __init__.py
│   │   └── monitor_processor.py
│   └── service/
│       ├── __init__.py
│       └── auth_service.py
└── tests/
    ├── __init__.py
    └── e2e/
        ├── __init__.py
        └── test_admin_controller.py
```

#### String Replacements to Make

In **ALL** files (except binary files), replace the following strings:

| Original | Replace With | Example |
|----------|--------------|---------|
| `My SaaS Skeleton` | Title Case version | `Moon Cake` |
| `my-saas-skeleton` | Kebab case version | `moon-cake` |
| `my_saas_skeleton` | Snake case version | `moon_cake` |
| `My SaaS application skeleton built with lessweb framework` | User's description | User's description |

#### Specific File Replacements

1. **pyproject.toml**:
   - `name = "my-saas-skeleton"` → `name = "{kebab-case}"`
   - `description = "My SaaS application skeleton built with lessweb framework"` → `description = "{user_description}"`

2. **main.py**:
   - `description='My SaaS Skeleton'` → `description='{Title Case}'`

3. **openapi/openapi.json**:
   - `"title": "My SaaS Skeleton API"` → `"title": "{Title Case} API"`
   - `"description": "My SaaS application skeleton built with lessweb framework - providing admin authentication and system monitoring"` → `"description": "{user_description}"`

4. **README.md**:
   - `# My SaaS Skeleton` → `# {Title Case}`
   - All other occurrences of "My SaaS Skeleton" → Title Case
   - All occurrences of "my-saas-skeleton" → Kebab case

5. **.gitlab-ci.yml**:
   - `APP_NAME: my-saas-skeleton` → `APP_NAME: {kebab-case}`

6. **config/lessweb.toml**:
   - `name = 'my-saas-skeleton'` → `name = '{kebab-case}'`
   - `file = 'logs/my-saas-skeleton.log'` → `file = 'logs/{kebab-case}.log'`

### Step 7: Verify and Report

1. After copying all files, report to the user:
   - Total number of files created
   - Target directory location
   - Next steps (installation, configuration, etc.)

2. Suggest next steps:
   ```
   Next steps:
   1. cd {target_directory}
   2. pip install -r requirements.txt
   3. Configure your .env file with database and Redis credentials
   4. Run database migrations: make pyway-migrate
   5. Start the application: python main.py
   ```

## Important Notes

- **Template Location**: The template directory is bundled with this skill at `~/.agents/skills/lessweb-starter/template/`
- **DO NOT** modify any business logic or functionality from the template
- **ONLY** replace project name strings as specified
- Preserve all file permissions and directory structure
- All Python files, config files, and documentation should be copied
- Ensure all occurrences of the old project name are replaced
- This skill is self-contained and can be shared with others - just share the entire `lessweb-starter/` directory
- Try to use Bash tool as much as possible to replace variable names and file names.

## Example Workflow

**User**: "Create a new project called '月饼商城'"

**Assistant**: "I've translated your project name to 'Moon Cake Mall'. Is this acceptable?"

**User**: "Yes"

**Assistant**: "I notice the name ends with 'Mall'. I'll remove that suffix. The project code will be 'Moon Cake'."

**Assistant**: "Please provide a project description (this will be used in pyproject.toml and openapi.json). If you don't have one, I can use: 'Moon Cake - A SaaS application built with lessweb framework'"

**User**: "An e-commerce platform for selling moon cakes online"

**Assistant**: "Where would you like to create the new project? (provide full path, or '.' for current directory)"

**User**: "/Users/zhangji/projects/moon-cake"

**Assistant**: *Creates the project structure with all files, replacing:*
- "My SaaS Skeleton" → "Moon Cake"
- "my-saas-skeleton" → "moon-cake"
- "my_saas_skeleton" → "moon_cake"
- Description → "An e-commerce platform for selling moon cakes online"

**Assistant**: "Project created successfully! 37 files created in /Users/zhangji/projects/moon-cake"

## Validation Checklist

Before completing the skill execution, verify:
- [ ] All files from example directory are copied
- [ ] Project name is in correct format (Title Case, kebab-case, snake_case)
- [ ] No technical suffixes in project name (API, Backend, etc.)
- [ ] Description is set in pyproject.toml and openapi.json
- [ ] All occurrences of "my-saas-skeleton" are replaced
- [ ] All occurrences of "My SaaS Skeleton" are replaced
- [ ] All occurrences of "my_saas_skeleton" are replaced
- [ ] config/lessweb.toml has correct logger name and file path
- [ ] .gitlab-ci.yml has correct APP_NAME
- [ ] README.md has correct project name in title and text
