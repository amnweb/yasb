# Contributing to YASB

Thank you for your interest in contributing to YASB! This guide will help you get started with the development workflow and coding standards.

## Getting Started

### Prerequisites

- Python 3.14 or higher
- Git
- A Windows development environment (YASB is Windows-only)

### Setting up Development Environment

1. **Fork and Clone the Repository**
   ```bash
   git clone https://github.com/amnweb/yasb.git
   cd yasb
   ```

2. **Install Development Dependencies**
   ```bash
   pip install -e .[dev]
   ```

3. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```
4. **VS Code Setup (Recommended)**
   The project includes VS Code workspace configuration in [.vscode/](https://github.com/amnweb/yasb/blob/main/.vscode/):
   
   - **Recommended Extensions** ([.vscode/extensions.json](https://github.com/amnweb/yasb/blob/main/.vscode/extensions.json)):
     - `charliermarsh.ruff` - Ruff linter and formatter
     - `ms-python.python` - Python language support
     - `ms-python.vscode-pylance` - Advanced Python IntelliSense
     - `ms-python.debugpy` - Python debugging

   - **Workspace Settings** ([.vscode/settings.json](https://github.com/amnweb/yasb/blob/main/.vscode/settings.json)):
     - Excludes `__pycache__` directories from file explorer and search
     - Configures Ruff as the default Python formatter
     - Enables auto-fix and import organization on save

    VS Code will automatically suggest installing the recommended extensions when you open the project.


## Development Workflow

### Code Quality Tools

YASB uses several tools to maintain code quality:

- **Ruff**: Fast Python linter and formatter
- **Pre-commit**: Git hooks for automated code quality checks
- **GitHub Actions**: Automated CI/CD workflows

### Pre-commit Configuration

The [.pre-commit-config.yaml](https://github.com/amnweb/yasb/blob/main/.pre-commit-config.yaml) includes:
- Ruff linting and formatting with auto-fix enabled

### Linting and Formatting

Before committing your changes:

```bash
# Format code with Ruff
ruff format .

# Check linting
ruff check .

# Fix auto-fixable issues
ruff check --fix .
```

### Project Structure

```
yasb/
├── src/
│   ├── core/
│   │   ├── widgets/         # Widget implementations
│   │   └── validation/      # Widget validation schemas
│   ├── config.yaml          # Default configuration
│   ├── styles.css           # Default styles
│   └── main.py              # Application entry point
├── docs/                    # Documentation
├── demo/                    # Demo images
├── .github/                 # GitHub workflows and templates
├── pyproject.toml           # Project configuration
└── README.md
```

## Contributing Guidelines

### Types of Contributions

1. **Bug Fixes**: Fix existing issues
2. **New Widgets**: Add new widget functionality
3. **Documentation**: Improve or add documentation
4. **Performance**: Optimize existing code
5. **Features**: Add new application features


### AI-Generated Code Policy

If you use AI tools (e.g., GitHub Copilot, ChatGPT, or similar) to generate code for your pull request, you **must**:

1. **Understand the codebase** before submitting. AI-generated code often lacks context about project conventions, architecture, and existing patterns.
2. **Review every line** of the generated code. Do not blindly push AI output without verifying correctness, style, and compatibility with the project.
3. **Test your changes thoroughly** to ensure they work as expected and do not introduce regressions.
4. **Follow the project's coding standards** AI tools may not respect Ruff rules, naming conventions, or the project structure.

> **Pull requests that appear to be untested, unreviewed AI-generated code will be closed without review.**

We welcome contributions that leverage AI as an assistive tool, but the contributor is fully responsible for the quality and correctness of the submitted code.

### Creating a New Widget
Follow the [Writing Widget](https://github.com/amnweb/yasb/wiki/Writing-Widget) guide for detailed instructions.