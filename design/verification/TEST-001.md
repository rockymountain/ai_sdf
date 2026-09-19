---
id: TEST-001
kind: verification
title: Async indexing integration verification
status: verified
version: 1
verification_type: integration
---

# Verification

Automated tests assert that accepting a document queues an indexing request and returns before the worker processes the job.
