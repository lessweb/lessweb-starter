# Lessweb Starter Skill

An AI Agent skill for creating new Lessweb projects from a template.

## What This Skill Does

This skill automates the process of creating a new Lessweb project by:
1. Collecting project name and description from the user
2. Translating Chinese project names to English if needed
3. Validating and cleaning project names (removing technical suffixes)
4. Copying the complete project template
5. Replacing all occurrences of the template project name with the new project name
6. Creating a ready-to-run Lessweb application

## Installation

### Option 1: Direct Copy
Copy the entire `lessweb-starter/` directory to your Agent skills directory:
```bash
cp -r lessweb-starter ~/.agents/skills/
```

### Option 2: Manual Installation
1. Create the skill directory:
   ```bash
   mkdir -p ~/.agents/skills/lessweb-starter
   ```

2. Copy all files including the template:
   ```bash
   cp -r lessweb-starter/* ~/.agents/skills/lessweb-starter/
   ```

## Directory Structure

```
lessweb-starter/
├── SKILL.md           # Main skill instructions for AI Agents
├── README.md          # This file (documentation for humans)
└── template/          # Complete Lessweb project template
    ├── config/        # Configuration files
    ├── shared/        # Shared modules and plugins
    ├── src/           # Source code
    │   ├── controller/
    │   ├── entity/
    │   ├── processor/
    │   └── service/
    ├── tests/         # Test files
    ├── migration/     # Database migration scripts
    ├── openapi/       # OpenAPI specification
    └── ...            # Other project files
```

## Usage

After installation, you can create a new Lessweb project by asking AI agent (Deep Code/Claude Code/Codex):

- "Create a new Lessweb project"
- "Start a new project with Lessweb"
- "Use the lessweb-starter skill to create a project"

AI agent will guide you through the process interactively.

## Template Information

The template is based on the Lessweb example project and includes:
- **Admin Authentication**: JWT-based authentication with Redis
- **Database Management**: MySQL with async operations via commondao
- **Database Migrations**: Automated schema migrations using pyway
- **Task Queue**: Background job processing with BullMQ
- **System Monitoring**: Scheduled health checks
- **API Documentation**: Auto-generated OpenAPI/Swagger specs
- **Testing**: Comprehensive E2E tests with pytest

## Requirements

The generated projects require:
- Python 3.11+
- MySQL 5.7+
- Redis 6.0+

## Sharing This Skill

This skill is completely self-contained. To share it with others:

1. Compress the directory:
   ```bash
   tar -czf lessweb-starter.tar.gz -C ~/.agents/skills lessweb-starter
   ```

2. Share the compressed file

3. Recipients can extract it to their skills directory:
   ```bash
   tar -xzf lessweb-starter.tar.gz -C ~/.agents/skills/
   ```
## Versioning of `template`

The versioned `template/` development project is at: https://github.com/lessweb/lessweb-example

## License

MIT
