/**
 * API client for the workout tracker backend.
 */
const API = {
    baseUrl: '',

    /**
     * Get headers for API requests, including auth token if available.
     */
    async getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
        };

        // Add auth token if available
        if (window.Auth) {
            try {
                const token = await window.Auth.getAccessToken();
                if (token) {
                    headers['Authorization'] = `Bearer ${token}`;
                }
            } catch (error) {
                console.error('Failed to get access token:', error);
                // Continue without token - let backend return 401 if needed
            }
        }

        return headers;
    },

    /**
     * Emit an event to the backend.
     */
    async emitEvent(eventType, payload) {
        const headers = await this.getHeaders();
        
        const response = await fetch(`${this.baseUrl}/api/events`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                event_type: eventType,
                payload: payload
            })
        });

        if (!response.ok) {
            // Handle 401 Unauthorized
            if (response.status === 401) {
                throw new Error('Authentication required. Please log in.');
            }

            // Read response body as text first
            const text = await response.text();

            // Try to parse as JSON
            try {
                const error = JSON.parse(text);
                throw new Error(error.detail || 'Failed to emit event');
            } catch (e) {
                // Response is not JSON (e.g., HTML 500 page)
                throw new Error(`Server error (${response.status}): ${text.substring(0, 100)}`);
            }
        }

        return response.json();
    },

    /**
     * Get a projection.
     */
    async getProjection(key) {
        const headers = await this.getHeaders();
        
        const response = await fetch(`${this.baseUrl}/api/projections/${key}`, { headers });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Authentication required. Please log in.');
            }
            throw new Error('Failed to get projection');
        }

        const result = await response.json();
        return result.data;
    },

    /**
     * List events.
     */
    async listEvents(eventType = null, limit = 100) {
        const headers = await this.getHeaders();
        
        let url = `${this.baseUrl}/api/events?limit=${limit}`;
        if (eventType) {
            url += `&event_type=${eventType}`;
        }

        const response = await fetch(url, { headers });

        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Authentication required. Please log in.');
            }
            throw new Error('Failed to list events');
        }

        const result = await response.json();
        return result.events;
    },

    /**
     * Get all exercises.
     * Note: This endpoint is public (no auth required).
     */
    async getExercises() {
        const response = await fetch(`${this.baseUrl}/api/exercises`);

        if (!response.ok) {
            throw new Error('Failed to get exercises');
        }

        const result = await response.json();
        return result.exercises;
    }
};
