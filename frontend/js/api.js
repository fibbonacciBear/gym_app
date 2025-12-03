/**
 * API client for the workout tracker backend.
 */
const API = {
    baseUrl: '',

    /**
     * Emit an event to the backend.
     */
    async emitEvent(eventType, payload) {
        const response = await fetch(`${this.baseUrl}/api/events`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_type: eventType,
                payload: payload
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to emit event');
        }

        return response.json();
    },

    /**
     * Get a projection.
     */
    async getProjection(key) {
        const response = await fetch(`${this.baseUrl}/api/projections/${key}`);

        if (!response.ok) {
            throw new Error('Failed to get projection');
        }

        const result = await response.json();
        return result.data;
    },

    /**
     * List events.
     */
    async listEvents(eventType = null, limit = 100) {
        let url = `${this.baseUrl}/api/events?limit=${limit}`;
        if (eventType) {
            url += `&event_type=${eventType}`;
        }

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error('Failed to list events');
        }

        const result = await response.json();
        return result.events;
    }
};
