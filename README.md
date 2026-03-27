# smart-locator

`smart-locator` is a Python package for discovering, scoring, validating, and generating Selenium locators from a live page.

## Install

```bash
pip install smart-locator
```

## Quick start

```python
from smart_locator import SmartLocator

sl = SmartLocator(driver)
print(sl.suggest("login form"))
```
