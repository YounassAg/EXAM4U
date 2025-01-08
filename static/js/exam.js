document.addEventListener('DOMContentLoaded', function () {
    let questionCount = parseInt(document.getElementById('question_count')?.value || 0);

    // Function to safely remove a question
    function removeQuestion(questionId) {
        const questionElement = document.getElementById(`question_${questionId}`);
        if (questionElement) {
            questionElement.remove();
            questionCount--;
            const questionCountInput = document.getElementById('question_count');
            if (questionCountInput) {
                questionCountInput.value = questionCount;
            }
            reindexQuestions();
        }
    }

    // Function to handle question type changes
    function handleQuestionTypeChange(event) {
        const questionId = event.target.getAttribute('data-question-id');
        if (!questionId) return;

        const mcqSection = document.getElementById(`mcq_section_${questionId}`);
        if (!mcqSection) return;

        mcqSection.classList.toggle('hidden', event.target.value !== 'MCQ');
    }

    // Function to reindex questions
    function reindexQuestions() {
        const questionsContainer = document.getElementById('questions-container');
        if (!questionsContainer) return;

        const questionDivs = Array.from(questionsContainer.children);
        questionDivs.forEach((questionDiv, index) => {
            const newIndex = index + 1;
            
            // Update question div ID
            questionDiv.id = `question_${newIndex}`;
            
            // Update question title
            const titleElement = questionDiv.querySelector('h2');
            if (titleElement) {
                titleElement.textContent = `Question ${newIndex}`;
            }

            // Update all input/select fields
            questionDiv.querySelectorAll('input, select, textarea').forEach(element => {
                const oldName = element.getAttribute('name');
                const oldId = element.getAttribute('id');
                if (oldName) {
                    element.setAttribute('name', oldName.replace(/\d+/, newIndex));
                }
                if (oldId) {
                    element.setAttribute('id', oldId.replace(/\d+/, newIndex));
                }
            });

            // Update data-question-id attributes
            questionDiv.querySelectorAll('[data-question-id]').forEach(element => {
                element.setAttribute('data-question-id', newIndex);
            });

            // Update MCQ section ID if it exists
            const mcqSection = questionDiv.querySelector('.mcq-choices-section');
            if (mcqSection) {
                mcqSection.id = `mcq_section_${newIndex}`;
            }

            // Update MCQ choices container ID if it exists
            const mcqChoicesContainer = questionDiv.querySelector('.mcq-choices-container');
            if (mcqChoicesContainer) {
                mcqChoicesContainer.id = `mcq_choices_${newIndex}`;
            }
        });

        // Update the question count input
        const questionCountInput = document.getElementById('question_count');
        if (questionCountInput) {
            questionCountInput.value = questionDivs.length;
        }
    }

    // Function to attach event listeners
    function attachEventListeners() {
        // Remove question button listeners
        document.querySelectorAll('.remove-question-btn').forEach(button => {
            // Remove existing listeners first
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            // Add new listener
            newButton.addEventListener('click', function() {
                const questionId = this.getAttribute('data-question-id');
                if (questionId) {
                    removeQuestion(questionId);
                }
            });
        });

        // Add MCQ choice button listeners
        document.querySelectorAll('.add-mcq-choice-btn').forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);
            
            newButton.addEventListener('click', function() {
                const questionId = this.getAttribute('data-question-id');
                if (questionId) {
                    addMCQChoice(questionId);
                }
            });
        });

        // Add question type change listeners
        document.querySelectorAll('select[id^="question_type_"]').forEach(select => {
            select.addEventListener('change', handleQuestionTypeChange);
        });
    }

    // Initial setup
    attachEventListeners();

    // Initialize question types
    document.querySelectorAll('select[id^="question_type_"]').forEach(select => {
        const questionId = select.getAttribute('data-question-id');
        if (questionId) {
            const mcqSection = document.getElementById(`mcq_section_${questionId}`);
            if (mcqSection) {
                mcqSection.classList.toggle('hidden', select.value !== 'MCQ');
            }
        }
    });
}); 