/**
 * Main workout app using Alpine.js
 */
function workoutApp() {
    return {
        // State
        currentWorkout: null,
        statusMessage: '',
        statusType: 'success',

        // Initialize
        async init() {
            await this.loadCurrentWorkout();
        },

        // Load current workout from projection
        async loadCurrentWorkout() {
            try {
                this.currentWorkout = await API.getProjection('current_workout');
            } catch (error) {
                console.error('Failed to load current workout:', error);
            }
        },

        // Start a new workout
        async startWorkout() {
            try {
                const result = await API.emitEvent('WorkoutStarted', {});
                this.showStatus('Workout started!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to start workout: ' + error.message, 'error');
            }
        },

        // Finish the current workout
        async finishWorkout() {
            if (!this.currentWorkout) return;

            try {
                await API.emitEvent('WorkoutCompleted', {
                    workout_id: this.currentWorkout.id
                });
                this.showStatus('Workout saved!', 'success');
                this.currentWorkout = null;
            } catch (error) {
                this.showStatus('Failed to finish workout: ' + error.message, 'error');
            }
        },

        // Discard the current workout
        async discardWorkout() {
            if (!this.currentWorkout) return;

            if (!confirm('Discard this workout? All data will be lost.')) {
                return;
            }

            try {
                await API.emitEvent('WorkoutDiscarded', {
                    workout_id: this.currentWorkout.id
                });
                this.showStatus('Workout discarded', 'success');
                this.currentWorkout = null;
            } catch (error) {
                this.showStatus('Failed to discard workout: ' + error.message, 'error');
            }
        },

        // Show status message
        showStatus(message, type = 'success') {
            this.statusMessage = message;
            this.statusType = type;
            setTimeout(() => {
                this.statusMessage = '';
            }, 3000);
        }
    };
}
