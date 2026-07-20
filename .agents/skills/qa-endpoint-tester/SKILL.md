---
name: qa-endpoint-tester
description: Use this skill when generating tests. It ensures all tests are created as endpoint tests formatted as Postman Collection JSON so they can be imported and run in Postman.
---

# QA Endpoint Tester Guidelines

When tasked with writing tests, you must act as an API QA tester. Strictly adhere to the following rules:

## 1. Focus Exclusively on Endpoint Testing
- All tests you generate must be API endpoint tests.
- Do not write traditional unit tests (e.g., pytest or Jest) unless explicitly requested.
- Focus on verifying status codes, request/response bodies, headers, and authentication.

## 2. Postman JSON Output
- You must output the tests in the form of a **Postman Collection JSON format** (v2.1.0).
- Provide the raw JSON in a code block so the user can easily copy it, save it as a `.json` file, and import it directly into Postman.

## 3. Comprehensive Scenarios
For every endpoint you test, include multiple scenarios as distinct Postman items:
- **Positive Test:** Valid inputs expecting a successful response (e.g., 200 OK, 201 Created).
- **Negative Tests:** Invalid parameters, missing required fields, or unauthorized access expecting the correct error codes (e.g., 400 Bad Request, 401 Unauthorized, 404 Not Found).

## 4. Include Assertions (Postman Scripts)
- Within the Postman JSON structure, utilize the `events` array to write Postman test scripts (JavaScript).
- Automatically assert the expected status code (`pm.response.to.have.status()`).
- Automatically assert the presence and types of expected fields in the response body.
