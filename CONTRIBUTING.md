# Contributing to lexdiff

Thank you for your interest in contributing to lexdiff! This project aims to make Japanese law amendment history accessible to everyone through GitHub-style diff visualization.

## What We Accept

- Bug fixes and UI/UX improvements
- Data pipeline enhancements (new laws, better diff algorithms)
- Accessibility, performance, and infrastructure improvements
- Documentation improvements and translations

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/wharfe/lex-diff/issues) to report bugs or suggest features
- Include steps to reproduce for bugs
- For feature requests, explain the use case

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run linting (`cd frontend && npm run lint`)
5. Commit with a clear message
6. Push and open a Pull Request

### Development Setup

```bash
git clone https://github.com/wharfe/lex-diff.git
cd lex-diff

# Python pipeline
uv sync

# Frontend
cd frontend
npm install
npm run dev -- -p 3002
```

## Guidelines

### Code

- TypeScript strict mode
- Code comments in English
- User-facing text in Japanese
- Use Tailwind CSS for styling
- Follow existing patterns in the codebase

### AI Prompts

Changes to AI prompts (summarization, annotation, etc.) require extra scrutiny:

- Explain the reasoning for the change
- Show before/after examples of generated output
- Changes to prompts should be reviewed by at least one other contributor

### Commits

- Use clear, descriptive commit messages
- Reference issue numbers where applicable

## Areas Where Help Is Needed

- Adding more laws and generating diffs
- Frontend components and UI improvements
- Accessibility (a11y) enhancements
- Performance optimization
- Documentation and translations
- AI prompt refinement
- Testing

## Questions?

Open a [GitHub Issue](https://github.com/wharfe/lex-diff/issues).
