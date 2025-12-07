# 📦 PyPI Publishing Guide

Package built and ready to publish! ✅

---

## 📊 Package Details

- **Name**: `openkeywords`
- **Version**: `1.0.0`
- **Built**: ✅ Successfully built
- **Validated**: ✅ Passed twine checks
- **Wheel**: `openkeywords-1.0.0-py3-none-any.whl` (43KB)
- **Source**: `openkeywords-1.0.0.tar.gz` (94KB)

---

## 🚀 How to Publish to PyPI

### Option 1: Test PyPI First (Recommended)

Test the package on Test PyPI before publishing to the real PyPI:

```bash
# 1. Create account on Test PyPI (if you haven't)
# Go to: https://test.pypi.org/account/register/

# 2. Upload to Test PyPI
python3 -m twine upload --repository testpypi dist/*

# 3. Test installation
pip install --index-url https://test.pypi.org/simple/ --no-deps openkeywords

# 4. Test the CLI
openkeywords --help
```

### Option 2: Publish to PyPI Directly

Once you're confident:

```bash
# 1. Create account on PyPI (if you haven't)
# Go to: https://pypi.org/account/register/

# 2. Upload to PyPI
python3 -m twine upload dist/*

# You'll be prompted for:
# - Username: __token__
# - Password: pypi-... (your API token)
```

### Setting Up API Token (Recommended)

Instead of using username/password, use an API token:

1. Go to https://pypi.org/manage/account/token/
2. Create a new API token
3. Save it securely
4. Use it when prompted:
   - Username: `__token__`
   - Password: `pypi-AgEIcHlwaS5vcmcC...` (your token)

Or save in `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcC...
```

---

## ✅ Pre-Publish Checklist

- ✅ Package builds successfully
- ✅ Twine check passes
- ✅ Version updated to 1.0.0
- ✅ README.md is comprehensive
- ✅ CHANGELOG.md exists
- ✅ LICENSE file included
- ✅ GitHub release created
- ✅ All tests pass
- ✅ No sensitive data in code

---

## 📦 After Publishing

### 1. Test Installation
```bash
# Wait a few minutes for PyPI to index
pip install openkeywords

# Test it works
openkeywords --help
```

### 2. Update README Badge
Add PyPI badge to README.md:

```markdown
[![PyPI version](https://badge.fury.io/py/openkeywords.svg)](https://badge.fury.io/py/openkeywords)
[![Downloads](https://pepy.tech/badge/openkeywords)](https://pepy.tech/project/openkeywords)
```

### 3. Announce It!
- 🐦 Twitter/X announcement
- 💼 LinkedIn post
- 📰 Dev.to blog post
- 🔗 Share on Reddit (r/Python, r/SEO)
- 📱 Product Hunt launch

### 4. Monitor
- Watch PyPI download stats: https://pypistats.org/packages/openkeywords
- Check for issues: https://github.com/federicodeponte/openkeyword/issues
- Respond to community feedback

---

## 🔄 Updating the Package

For future releases:

```bash
# 1. Update version in pyproject.toml
# 2. Update CHANGELOG.md
# 3. Commit changes
git add pyproject.toml CHANGELOG.md
git commit -m "Bump version to X.Y.Z"
git push

# 4. Create GitHub release
gh release create vX.Y.Z --title "vX.Y.Z" --notes "Release notes"

# 5. Clean old builds
rm -rf dist/

# 6. Build new packages
python3 -m build

# 7. Upload to PyPI
python3 -m twine upload dist/*
```

---

## 📚 Resources

- **PyPI Project Page**: https://pypi.org/project/openkeywords (after publishing)
- **Test PyPI**: https://test.pypi.org/
- **Packaging Guide**: https://packaging.python.org/
- **Twine Docs**: https://twine.readthedocs.io/

---

## 🎉 Ready to Publish!

Your package is ready. Run this command when you're ready:

```bash
python3 -m twine upload dist/*
```

Or test first:

```bash
python3 -m twine upload --repository testpypi dist/*
```

Good luck! 🚀

