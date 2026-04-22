# Contributing to PDF Extractor

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive in all interactions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/pdf-extractor.git
   cd pdf-extractor
   ```
3. **Create a virtual environment**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Unix
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Making Changes

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** with clear, focused commits:
   ```bash
   git commit -m "Brief description of changes"
   ```

3. **Test your changes**:
   ```bash
   python batch_extract.py --help
   python -m py_compile batch_extract.py
   ```

4. **Update documentation** if needed:
   - Update relevant files in `docs/`
   - Update `README.md` if adding features
   - Update docstrings in code

5. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request** on GitHub with:
   - Clear title and description
   - Reference to any related issues
   - Summary of changes

## Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Include tests/validation for your changes
- Update documentation to match new behavior
- Follow existing code style
- Ensure all files compile successfully: `python -m py_compile batch_extract.py`

## Code Style

- Use clear, descriptive variable names
- Keep functions focused and maintainable
- Add comments only for non-obvious logic (WHY, not WHAT)
- Follow PEP 8 conventions

## Quality Standards

The project maintains strict quality standards:
- Zero data loss on crashes (atomic writes)
- No silent failures (all errors logged)
- Comprehensive error handling
- Full test coverage for critical paths

## Reporting Issues

Use GitHub Issues to report:
- **Bugs**: Include reproducible steps and expected vs actual behavior
- **Feature requests**: Describe the use case and desired behavior
- **Documentation**: Point out unclear sections

## Questions?

Feel free to open an issue with the `question` label or check existing discussions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
