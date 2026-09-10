# CAPSIM Analyzer

WIP -- Version 1 defines the local, validated data foundation for CAPSIM Courier reports.

The eventual workflow is:

```text
Courier PDF -> PDF parser -> validated Python data model -> versioned JSON
             -> analysis / forecasting / recommendations
```

While still in progress, the purpose of this program is to analyze the Courier PDF from CAPSIM Simulations
on a weekly basis and be able to provide accurate and helpful estimations for our team while considering other 
teams investments. Through thorough forecast and market prediction analysis, the program shall provide insight 
and recommendations on which direction to take throughout the simulation based off of previous round results.