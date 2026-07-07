export const testingApi = {
    async runTests(testType, cases) {
        const response = await fetch('http://localhost:8000/api/v1/tests/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ test_type: testType, cases }),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to run tests');
        }
        return response.json();
    },

    async getHistory() {
        const response = await fetch('http://localhost:8000/api/v1/tests/history');
        if (!response.ok) {
            throw new Error('Failed to fetch test history');
        }
        return response.json();
    },

    async getRunDetails(runId) {
        const response = await fetch(`http://localhost:8000/api/v1/tests/runs/${runId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch run details');
        }
        return response.json();
    }
};
