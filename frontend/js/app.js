/**
 * Main workout app using Alpine.js
 */
function workoutApp() {
    return {
        // State
        activeTab: 'workout',
        currentWorkout: null,
        allExercises: [],
        workoutHistory: [],
        historyLoading: false,
        selectedWorkout: null,
        statusMessage: '',
        statusType: 'success',
        showExerciseSelector: false,
        showSetLogger: false,
        selectedExerciseId: null,
        setForm: {
            weight: '',
            reps: '',
            unit: 'kg'
        },

        // Initialize
        async init() {
            await this.loadExercises();
            await this.loadCurrentWorkout();
        },

        // Load all exercises from the library
        async loadExercises() {
            try {
                this.allExercises = await API.getExercises();
            } catch (error) {
                console.error('Failed to load exercises:', error);
            }
        },

        // Load current workout from projection
        async loadCurrentWorkout() {
            try {
                this.currentWorkout = await API.getProjection('current_workout');
            } catch (error) {
                console.error('Failed to load current workout:', error);
            }
        },

        // Get exercise name by ID
        getExerciseName(exerciseId) {
            const exercise = this.allExercises.find(ex => ex.id === exerciseId);
            return exercise ? exercise.name : exerciseId;
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

        // Add exercise to workout
        async addExercise(exerciseId) {
            if (!this.currentWorkout) return;

            try {
                await API.emitEvent('ExerciseAdded', {
                    workout_id: this.currentWorkout.id,
                    exercise_id: exerciseId
                });
                this.showExerciseSelector = false;
                this.showStatus('Exercise added!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to add exercise: ' + error.message, 'error');
            }
        },

        // Select exercise to log a set
        selectExerciseForSet(exerciseId) {
            this.selectedExerciseId = exerciseId;

            // Prefill with last set values if available
            const exercise = this.currentWorkout.exercises.find(ex => ex.exercise_id === exerciseId);
            if (exercise && exercise.sets.length > 0) {
                const lastSet = exercise.sets[exercise.sets.length - 1];
                this.setForm.weight = lastSet.weight;
                this.setForm.reps = lastSet.reps;
                this.setForm.unit = lastSet.unit;
            } else {
                this.setForm.weight = '';
                this.setForm.reps = '';
                this.setForm.unit = 'kg';
            }

            this.showSetLogger = true;
        },

        // Log a set
        async logSet() {
            if (!this.currentWorkout) return;

            try {
                await API.emitEvent('SetLogged', {
                    workout_id: this.currentWorkout.id,
                    exercise_id: this.selectedExerciseId,
                    weight: parseFloat(this.setForm.weight),
                    reps: parseInt(this.setForm.reps),
                    unit: this.setForm.unit
                });
                this.showSetLogger = false;
                this.showStatus('Set logged!', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to log set: ' + error.message, 'error');
            }
        },

        // Delete a set
        async deleteSet(eventId) {
            if (!this.currentWorkout) return;

            if (!confirm('Delete this set?')) {
                return;
            }

            try {
                await API.emitEvent('SetDeleted', {
                    workout_id: this.currentWorkout.id,
                    original_event_id: eventId
                });
                this.showStatus('Set deleted', 'success');
                await this.loadCurrentWorkout();
            } catch (error) {
                this.showStatus('Failed to delete set: ' + error.message, 'error');
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
                await this.loadCurrentWorkout();
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
                await this.loadCurrentWorkout();
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
        },

        // Load workout history
        async loadHistory() {
            this.historyLoading = true;
            try {
                const response = await fetch('/api/history');
                if (!response.ok) {
                    throw new Error('Failed to load history');
                }
                this.workoutHistory = await response.json();
            } catch (error) {
                console.error('Failed to load history:', error);
                this.showStatus('Failed to load history', 'error');
            }
            this.historyLoading = false;
        },

        // Format date for display
        formatDate(isoString) {
            if (!isoString) return '';
            const date = new Date(isoString);
            return date.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric'
            });
        },

        // Format volume for display
        formatVolume(volume) {
            if (!volume) return '0 kg';
            if (volume >= 1000) {
                return (volume / 1000).toFixed(1) + 'k kg';
            }
            return Math.round(volume) + ' kg';
        }
    };
}
