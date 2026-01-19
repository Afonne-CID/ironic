Type Annotation Migration Template
===================================

Overview
--------

This document provides a reliable, repeatable process for migrating the Ironic
codebase to use Python type annotations. The goal is to create a template that,
once approved by core reviewers, can be followed by anyone to consistently
migrate any file, module, or the full project (gradually) to become type
annotated.

Core Principles
---------------

1. **Gradual Migration**: One file or module at a time, not the entire codebase
   at once. This makes reviews manageable and completion achievable.

2. **Code First, Tests Second**: Production code should be migrated before test
   code. This ensures the core functionality is properly typed before
   addressing test helpers.

3. **Tool-Assisted**: Use automated tools where possible (stubgen, monkeytype,
   ruff, pyright), but always with manual review and validation.

4. **Backward Compatible**: Type annotations must not break existing
   functionality. Annotations are ignored at runtime in Python.

5. **Reviewable**: Each migration should be a separate, reviewable change that
   can be easily understood and approved.

Prerequisites
-------------

Required Tools
~~~~~~~~~~~~~~

Add the following to ``test-requirements.txt``:

.. code-block:: text

   mypy>=1.0.0  # For stubgen and type checking
   monkeytype>=22.2.0  # For runtime type inference (optional)
   pyright>=1.1.0  # For validation (optional but recommended)

Configuration Files
~~~~~~~~~~~~~~~~~~~

Add the following to ``pyproject.toml`` (or create ``mypy.ini``):

.. code-block:: toml

   [tool.mypy]
   python_version = "3.10"
   warn_return_any = true
   warn_unused_configs = true
   disallow_untyped_defs = false  # Start permissive, tighten later
   disallow_incomplete_defs = false
   check_untyped_defs = true
   no_implicit_optional = true
   warn_redundant_casts = true
   warn_unused_ignores = true
   warn_no_return = true
   strict_optional = true
   show_error_codes = true

   # Per-module overrides for gradual migration
   [[tool.mypy.overrides]]
   module = [
       "ironic.common.utils",
       # Add migrated modules here
   ]
   disallow_untyped_defs = true

Migration Process: Step-by-Step
--------------------------------

Phase 1: Code Migration (Production Code First)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Step 1: Select Target File/Module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Choose a self-contained module or file
- Prefer files with good test coverage
- Start with utility modules (e.g., ``ironic/common/utils.py``)
- Avoid files with complex circular dependencies initially

Step 2: Generate Initial Type Stubs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Generate stub files to get a starting point for types:

.. code-block:: bash

   # Generate .pyi stub files (doesn't modify source)
   stubgen -p ironic.common.utils -o stubs/

   # Review generated stubs in stubs/ironic/common/utils.pyi
   # This gives you a starting point for types

**Note**: Review the generated stubs carefully. They provide hints but may not
always be accurate.

Step 3: Add Type Annotations to Source Code
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Add ``from __future__ import annotations`` at the top of the file (PEP 563)
- Add function parameter types: ``def func(param: str) -> bool:``
- Add return types: ``-> bool``
- Use ``typing`` module for complex types: ``List[str]``, ``Dict[str, Any]``,
  ``Optional[str]``
- Use ``TYPE_CHECKING`` for forward references if needed

Step 4: Validate with Type Checker
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Run type checking on the specific file:

.. code-block:: bash

   # Run mypy on the specific file
   mypy ironic/common/utils.py

   # Or use pyright for additional validation
   pyright ironic/common/utils.py

Step 5: Run Tests
^^^^^^^^^^^^^^^^^

Ensure all existing tests still pass:

.. code-block:: bash

   # Run tests for the specific module
   tox -e py3 -- ironic.tests.unit.common.test_utils

Step 6: Fix Type Errors
^^^^^^^^^^^^^^^^^^^^^^^^

- Address all type checker errors
- Use ``# type: ignore[error-code]`` sparingly and document why
- Prefer fixing types over ignoring errors
- Update docstrings if they conflict with type annotations

Phase 2: Test Migration (After Code is Complete)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Step 1: Annotate Test Functions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Add types to test helper functions first
- Then annotate test methods
- Mock objects can use ``mock.Mock`` with type hints

Step 2: Validate Test Types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   mypy ironic/tests/unit/common/test_utils.py

Step 3: Run Full Test Suite
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   tox -e py3

Example: Migrating ``is_valid_datapath_id()``
=============================================

Before (Current Code)
---------------------

.. code-block:: python

   def is_valid_datapath_id(datapath_id):
       """Verify the format of an OpenFlow datapath_id.

       Check if a datapath_id is valid and contains 16 hexadecimal digits.
       Datapath ID format: the lower 48-bits are for a MAC address,
       while the upper 16-bits are implementer-defined.

       :param datapath_id: OpenFlow datapath_id to be validated.
       :returns: True if valid. False if not.

       """
       m = "^[0-9a-f]{16}$"
       return (isinstance(datapath_id, str)
               and re.match(m, datapath_id.lower()))

After (Type Annotated)
----------------------

.. code-block:: python

   from __future__ import annotations

   from typing import Optional
   import re

   def is_valid_datapath_id(datapath_id: str) -> bool:
       """Verify the format of an OpenFlow datapath_id.

       Check if a datapath_id is valid and contains 16 hexadecimal digits.
       Datapath ID format: the lower 48-bits are for a MAC address,
       while the upper 16-bits are implementer-defined.

       :param datapath_id: OpenFlow datapath_id to be validated.
       :returns: True if valid. False if not.

       """
       m = "^[0-9a-f]{16}$"
       match_result: Optional[re.Match[str]] = re.match(m, datapath_id.lower())
       return match_result is not None

Key Changes:

1. Added ``from __future__ import annotations`` at module top
2. Added ``datapath_id: str`` parameter type
3. Added ``-> bool`` return type
4. Made ``re.match()`` result explicit with type annotation
5. Changed return logic to be more explicit about None check

Test File Migration
~~~~~~~~~~~~~~~~~~~

Before:

.. code-block:: python

   def test_is_valid_datapath_id(self):
       self.assertTrue(utils.is_valid_datapath_id("0000000000000001"))
       self.assertFalse(utils.is_valid_datapath_id("invalid"))

After:

.. code-block:: python

   def test_is_valid_datapath_id(self) -> None:
       self.assertTrue(utils.is_valid_datapath_id("0000000000000001"))
       self.assertFalse(utils.is_valid_datapath_id("invalid"))

Review Checklist
----------------

For reviewers, verify the following:

- [ ] ``from __future__ import annotations`` is at the top of the file
- [ ] All public functions have type annotations
- [ ] All return types are specified
- [ ] Complex types use appropriate ``typing`` imports (``List``, ``Dict``,
      ``Optional``, ``Union``, etc.)
- [ ] Type checker passes: ``mypy <file>`` shows no errors
- [ ] All existing tests pass: ``tox -e py3 -- <test_module>``
- [ ] No ``# type: ignore`` comments without justification
- [ ] Type annotations match docstrings (especially ``:param`` and ``:returns``)
- [ ] Forward references use ``TYPE_CHECKING`` when needed
- [ ] No runtime behavior changes (annotations are ignored at runtime)

Gradual Migration Strategy
---------------------------

1. **Start with Leaf Modules**: Begin with modules that have no dependencies on
   other untyped modules

2. **Work Inward**: Migrate dependencies before dependents

3. **Track Progress**: Maintain a list of migrated modules in ``pyproject.toml``

4. **CI Integration**: Add a mypy check job that only runs on migrated modules
   initially

5. **Documentation**: Update contributor guide with type annotation guidelines

Tool Usage Guidelines
---------------------

stubgen (mypy)
~~~~~~~~~~~~~~

- Use for initial type discovery
- Review generated stubs, don't blindly copy
- Helps identify obvious types
- Command: ``stubgen -p <module> -o stubs/``

monkeytype (Optional)
~~~~~~~~~~~~~~~~~~~~~

- Useful for runtime type inference
- Run on specific test files: ``monkeytype run -m pytest tests/unit/common/test_utils.py``
- Review before applying: ``monkeytype list-modules`` and ``monkeytype stub <module>``
- **Note**: May use older syntax; convert to modern syntax (PEP 563)

ruff
~~~~

- Already configured; will format type annotations
- Run: ``ruff check --fix ironic/common/utils.py``

pyright/mypy
~~~~~~~~~~~~

- Use for validation
- Run before committing
- Fix all errors before submitting for review

Common Patterns
---------------

Handling Optional Values
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from typing import Optional

   def process_data(data: Optional[str]) -> int:
       if data is None:
           return 0
       return len(data)

Handling Union Types
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from typing import Union

   def parse_value(value: Union[str, int]) -> int:
       if isinstance(value, str):
           return int(value)
       return value

Forward References
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from __future__ import annotations
   from typing import TYPE_CHECKING

   if TYPE_CHECKING:
       from ironic.objects import Node

   def process_node(node: Node) -> None:
       ...

Generic Types
~~~~~~~~~~~~~

.. code-block:: python

   from typing import List, Dict, Any

   def merge_dicts(dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
       ...

CI/CD Integration
-----------------

Add to ``.pre-commit-config.yaml``:

.. code-block:: yaml

   - repo: https://github.com/pre-commit/mirrors-mypy
     rev: v1.0.0
     hooks:
       - id: mypy
         args: [--config-file=pyproject.toml]
         additional_dependencies: [types-all]

Add to ``tox.ini``:

.. code-block:: ini

   [testenv:mypy]
   deps = mypy>=1.0.0
   commands = mypy ironic/common/utils.py  # Update as modules migrate

Success Criteria
----------------

A migration is complete when:

1. All functions in the target file/module have type annotations
2. ``mypy`` passes with no errors on that module
3. All existing tests pass
4. Code review is approved
5. Module is added to ``mypy.ini`` strict checking list

Next Steps
----------

1. Review this template with core reviewers
2. Select a pilot file (suggest: ``ironic/common/utils.py`` or a small utility
   module)
3. Create a proof-of-concept patch following this template
4. Iterate on the template based on pilot experience
5. Document approved template in contributor guide
6. Begin gradual migration across the codebase

Notes
-----

This template is a living document. It should be updated as the migration
progresses and patterns emerge. Feedback from core reviewers and contributors
is essential to refine this process.
