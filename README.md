# CAPSIM Analyzer

Version 1 defines the local, validated data foundation for CAPSIM Courier reports.

The eventual workflow is:

```text
Courier PDF -> PDF parser -> validated Python data model -> versioned JSON
             -> analysis / forecasting / recommendations
```

This version intentionally does not implement PDF parsing, forecasting, market scoring,
or recommendation logic.