# Contributing to Scraper

Thank you for your interest in contributing to the Optimized Web Scraper project! We welcome all contributions, whether they're bug reports, feature requests, documentation improvements, or code changes.

## Code of Conduct

Please review our [Code of Conduct](CODE_OF_CONDUCT.md) before participating in this community.

## How to Contribute

### Reporting Bugs

1. Check if the bug has already been reported in [Issues](https://github.com/arslanbasharat-o-o/Scraper/issues)
2. If not, create a new issue using the bug report template
3. Include:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment (OS, Node version, Python version)
   - Screenshots if applicable

### Requesting Features

1. Check existing issues to avoid duplicates
2. Create a new issue using the feature request template
3. Describe the use case and expected behavior
4. Provide examples or mockups if relevant

### Submitting Code Changes

#### Setup Development Environment

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/Scraper.git
cd Scraper

# Create a feature branch
git checkout -b feature/your-feature-name

# Install dependencies
npm install

# Verify setup
node -c server.js
python3 --version
```

#### Making Changes

1. **Create a feature branch**: `git checkout -b feature/amazing-feature`
2. **Write clean code**:
   - Follow existing code style
   - Add comments for complex logic
   - Use meaningful variable names
   - Keep functions focused and small

3. **Test your changes**:
   ```bash
   # Syntax validation
   node -c server.js
   
   # Manual testing
   node server.js
   ```

4. **Update documentation** if adding new features
5. **Commit with clear messages**:
   ```bash
   # Good commit messages
   git commit -m "feat: Add support for lazy-loaded images"
   git commit -m "fix: Handle timeout errors in image extraction"
   git commit -m "docs: Update API documentation"
   ```

#### Commit Message Guidelines

Use conventional commits format:

- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation only changes
- `style:` Changes that don't affect code meaning (formatting, semicolons)
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `perf:` Code change that improves performance
- `test:` Adding missing tests
- `chore:` Changes to build process, dependencies, etc.

#### Push and Create Pull Request

```bash
# Push your branch
git push origin feature/amazing-feature

# Create a pull request on GitHub
# Include:
# - Clear title and description
# - Link to related issues (#123)
# - Screenshot/demo if UI-related
# - Test results
```

### Code Style Guidelines

#### JavaScript

```javascript
// Use arrow functions
const handleScrape = async (url) => {
  try {
    // Code here
  } catch (error) {
    writeLog('error', error.message, 'scrape', jobId);
  }
};

// Use async/await, not `.then()`
const result = await driver.get(url);

// Add JSDoc comments for functions
/**
 * Extracts images from a product page
 * @param {WebDriver} driver - Selenium web driver
 * @param {string} url - Product URL
 * @returns {Promise<string[]>} Array of image URLs
 */
async function extractImages(driver, url) {
  // Implementation
}

// Use const for variables (not let/var unless needed)
const productLinks = document.querySelectorAll('a.product');

// Use template literals for strings
const message = `Processing ${productCount} products`;
```

#### Python

```python
#!/usr/bin/env python3
"""Module docstring - describe what this script does."""

import json
import sys
from pathlib import Path

def convert_image(image_url: str) -> dict:
    """
    Convert image to JPEG format.
    
    Args:
        image_url: URL or path to image file
        
    Returns:
        Dictionary with success/error status and data
    """
    try:
        # Implementation
        pass
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    # Entry point
    pass
```

### Review Process

1. A maintainer will review your PR
2. Address any feedback or requested changes
3. Keep commits clean and squash if needed
4. Once approved, it will be merged

## Project Structure

```
Scraper/
├── server.js                  # Main Express server
├── convert_image.py          # Python image conversion
├── create_zip.py             # Python ZIP compression
├── package.json              # Node dependencies
├── README.md                 # Project documentation
├── CONTRIBUTING.md           # This file
├── LICENSE                   # MIT License
├── .github/
│   ├── workflows/
│   │   └── ci.yml           # GitHub Actions CI/CD
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   └── PULL_REQUEST_TEMPLATE.md
└── docs/
    ├── API.md
    ├── CONFIGURATION.md
    └── TROUBLESHOOTING.md
```

## Testing Before Submit

- [ ] Code syntax is valid (`node -c server.js`)
- [ ] No console errors or warnings
- [ ] Commit messages follow conventions
- [ ] Updated documentation if needed
- [ ] Tested locally with `node server.js`
- [ ] No breaking changes to API

## Development Tips

### Debugging

```bash
# Enable verbose logging
DEBUG=* node server.js

# Monitor memory
node --expose-gc server.js

# Check Python syntax
python3 -m py_compile convert_image.py
```

### Common Tasks

**Add a new API endpoint:**
1. Add route in `server.js`
2. Document in README
3. Test with curl
4. Commit with `feat:` prefix

**Optimize image detection:**
1. Add new selector in `collectCandidateUrls()`
2. Test with sample product URLs
3. Update documentation

**Update Python script:**
1. Test locally: `python3 script.py`
2. Handle errors gracefully
3. Return JSON responses for Node.js integration

## Questions?

- 📖 Read [README.md](README.md) for project overview
- 🔍 Check existing [Issues](https://github.com/arslanbasharat-o-o/Scraper/issues)
- 💬 Start a [Discussion](https://github.com/arslanbasharat-o-o/Scraper/discussions)
- 📧 Contact: arslanbasharat.o.o@gmail.com

## Recognition

Contributors will be:
- Credited in README
- Added to commit history
- Mentioned in project announcements

Thank you for making Scraper better! 🎉
