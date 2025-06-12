#!/usr/bin/env python
"""
Test runner script for the Chat API tests.
This simplifies running tests for the chat application specifically.
"""

import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'collaboration_backend.settings'
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True)
    failures = test_runner.run_tests(["apps.chat.tests"])
    sys.exit(bool(failures))
