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

    // Function to remove an MCQ choice
    function removeMCQChoice(questionId, choiceId) {
        const choiceElement = document.getElementById(`mcq_choice_${questionId}_${choiceId}`);
        if (choiceElement) {
            choiceElement.remove();
            // Update choice count
            const choiceCountInput = document.getElementById(`mcq_choice_count_${questionId}`);
            if (choiceCountInput) {
                const currentCount = parseInt(choiceCountInput.value);
                choiceCountInput.value = currentCount - 1;
            }
            // Reindex remaining choices
            reindexMCQChoices(questionId);
        }
    }

    // Function to reindex MCQ choices
    function reindexMCQChoices(questionId) {
        const choicesContainer = document.getElementById(`mcq_choices_${questionId}`);
        if (!choicesContainer) return;

        const choiceDivs = Array.from(choicesContainer.querySelectorAll('div[id^="mcq_choice_"]'));
        choiceDivs.forEach((choiceDiv, index) => {
            const newIndex = index + 1;
            
            // Update choice div ID
            choiceDiv.id = `mcq_choice_${questionId}_${newIndex}`;
            
            // Update choice title
            const titleElement = choiceDiv.querySelector('h3');
            if (titleElement) {
                titleElement.textContent = `Choix ${newIndex}`;
            }

            // Update all input fields
            choiceDiv.querySelectorAll('input').forEach(element => {
                const oldName = element.getAttribute('name');
                const oldId = element.getAttribute('id');
                if (oldName) {
                    element.setAttribute('name', oldName.replace(/_\d+$/, `_${newIndex}`));
                }
                if (oldId) {
                    element.setAttribute('id', oldId.replace(/_\d+$/, `_${newIndex}`));
                }
            });

            // Update labels
            choiceDiv.querySelectorAll('label').forEach(element => {
                const forAttr = element.getAttribute('for');
                if (forAttr && forAttr.includes('mcq_choice_')) {
                    element.setAttribute('for', forAttr.replace(/_\d+$/, `_${newIndex}`));
                }
            });

            // Update remove button data-choice-id
            const removeButton = choiceDiv.querySelector('.remove-mcq-choice-btn');
            if (removeButton) {
                removeButton.setAttribute('data-choice-id', newIndex);
            }
        });
    }

    // Function to handle question type changes
    function handleQuestionTypeChange(event) {
        const questionId = event.target.getAttribute('data-question-id');
        if (!questionId) return;

        const mcqSection = document.getElementById(`mcq_section_${questionId}`);
        if (!mcqSection) return;

        mcqSection.classList.toggle('hidden', event.target.value !== 'MCQ');
    }

    // Function to add a new question
    function addQuestion() {
        questionCount++;
        const questionsContainer = document.getElementById('questions-container');
        if (!questionsContainer) return;

        const questionDiv = document.createElement('div');
        questionDiv.className = 'bg-white dark:bg-gray-800 rounded-xl shadow-lg border border-gray-200 dark:border-gray-700 p-6 space-y-6';
        questionDiv.id = `question_${questionCount}`;

        questionDiv.innerHTML = `
            <div class="flex flex-col sm:flex-row justify-between items-center gap-2">
                <h2 class="text-lg font-bold text-gray-900 dark:text-white">Question ${questionCount}</h2>
                <button type="button" class="remove-question-btn sm:w-32 group inline-flex items-center justify-center px-3 py-1.5 text-red-600 dark:text-red-400 hover:text-white dark:hover:text-white bg-transparent hover:bg-gradient-to-r hover:from-red-600 hover:to-pink-600 dark:hover:from-red-500 dark:hover:to-pink-500 rounded-lg transition-all duration-300 hover:shadow-[0_0_15px_rgba(239,68,68,0.25)] hover:-translate-y-0.5 space-x-1.5" data-question-id="${questionCount}">
                    <div class="p-1 rounded-lg bg-gradient-to-br from-red-500/10 to-pink-500/10 dark:from-red-400/5 dark:to-pink-400/5">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                    </div>
                    <span class="font-medium">Supprimer</span>
                </button>
            </div>
            
            <div>
                <label for="question_type_${questionCount}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Type de Question</label>
                <select name="question_type_${questionCount}" 
                        id="question_type_${questionCount}" 
                        required 
                        data-question-id="${questionCount}"
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                    <option value="MCQ">QCM</option>
                    <option value="short_answer">Réponse Courte</option>
                    <option value="open">Question Ouverte</option>
                </select>
            </div>

            <div>
                <label for="question_wording_${questionCount}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Énoncé</label>
                <textarea name="question_wording_${questionCount}" 
                            id="question_wording_${questionCount}" 
                            rows="3" 
                            required
                            class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"></textarea>
            </div>

            <div>
                <label for="question_points_${questionCount}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Points</label>
                <input type="number" 
                        step="0.5"
                        name="question_points_${questionCount}" 
                        id="question_points_${questionCount}" 
                        value="1" 
                        required 
                        class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>

            <!-- MCQ Choices Section -->
            <div class="mcq-choices-section" id="mcq_section_${questionCount}">
                <div class="mcq-choices-container space-y-4" id="mcq_choices_${questionCount}">
                    <input type="hidden" name="mcq_choice_count_${questionCount}" id="mcq_choice_count_${questionCount}" value="0">
                </div>
                <button type="button" class="add-mcq-choice-btn mt-4 sm:w-40 group inline-flex items-center justify-center px-3 py-1.5 text-blue-600 dark:text-blue-400 hover:text-white dark:hover:text-white bg-transparent hover:bg-gradient-to-r hover:from-blue-600 hover:to-purple-600 dark:hover:from-blue-500 dark:hover:to-purple-500 rounded-lg transition-all duration-300 hover:shadow-[0_0_15px_rgba(37,99,235,0.25)] hover:-translate-y-0.5 space-x-1.5" data-question-id="${questionCount}">
                    <div class="p-1 rounded-lg bg-gradient-to-br from-blue-500/10 to-purple-500/10 dark:from-blue-400/5 dark:to-purple-400/5">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                        </svg>
                    </div>
                    <span class="font-medium">Ajouter un Choix</span>
                </button>
            </div>
        `;

        questionsContainer.appendChild(questionDiv);
        
        // Update question count input
        const questionCountInput = document.getElementById('question_count');
        if (questionCountInput) {
            questionCountInput.value = questionCount;
        }

        // Attach event listeners to the new question
        attachEventListeners();
    }

    // Function to add a new MCQ choice
    function addMCQChoice(questionId) {
        const choicesContainer = document.getElementById(`mcq_choices_${questionId}`);
        if (!choicesContainer) return;

        const choiceCountInput = document.getElementById(`mcq_choice_count_${questionId}`);
        if (!choiceCountInput) return;

        const choiceCount = parseInt(choiceCountInput.value) + 1;
        choiceCountInput.value = choiceCount;

        const choiceDiv = document.createElement('div');
        choiceDiv.className = 'bg-gray-50 dark:bg-gray-700 rounded-lg p-4 space-y-4 mb-4';
        choiceDiv.id = `mcq_choice_${questionId}_${choiceCount}`;

        choiceDiv.innerHTML = `
            <div class="flex flex-col sm:flex-row justify-between items-center gap-2">
                <h3 class="text-md font-bold text-gray-900 dark:text-white">Choix ${choiceCount}</h3>
                <button type="button" class="remove-mcq-choice-btn sm:w-32 group inline-flex items-center justify-center px-3 py-1.5 text-red-600 dark:text-red-400 hover:text-white dark:hover:text-white bg-transparent hover:bg-gradient-to-r hover:from-red-600 hover:to-pink-600 dark:hover:from-red-500 dark:hover:to-pink-500 rounded-lg transition-all duration-300 hover:shadow-[0_0_15px_rgba(239,68,68,0.25)] hover:-translate-y-0.5 space-x-1.5" 
                        data-question-id="${questionId}" data-choice-id="${choiceCount}">
                    <div class="p-1 rounded-lg bg-gradient-to-br from-red-500/10 to-pink-500/10 dark:from-red-400/5 dark:to-pink-400/5">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                    </div>
                    <span class="font-medium">Supprimer</span>
                </button>
            </div>
            <div>
                <label for="mcq_choice_text_${questionId}_${choiceCount}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Texte du Choix</label>
                <input type="text" 
                    name="mcq_choice_text_${questionId}_${choiceCount}" 
                    id="mcq_choice_text_${questionId}_${choiceCount}" 
                    required 
                    class="w-full px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
            <div class="flex items-center space-x-2">
                <input type="checkbox" 
                    name="mcq_choice_correct_${questionId}_${choiceCount}" 
                    id="mcq_choice_correct_${questionId}_${choiceCount}"
                    class="w-4 h-4 text-blue-600 border-gray-300 dark:border-gray-600 rounded focus:ring-blue-500">
                <label for="mcq_choice_correct_${questionId}_${choiceCount}" class="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Réponse Correcte
                </label>
            </div>
        `;

        choicesContainer.appendChild(choiceDiv);
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

    // Event delegation for dynamic elements
    document.addEventListener('click', function(e) {
        // Handle remove MCQ choice button clicks
        if (e.target.closest('.remove-mcq-choice-btn')) {
            const button = e.target.closest('.remove-mcq-choice-btn');
            const questionId = button.getAttribute('data-question-id');
            const choiceId = button.getAttribute('data-choice-id');
            if (questionId && choiceId) {
                removeMCQChoice(questionId, choiceId);
            }
        }
        
        // Handle remove question button clicks
        if (e.target.closest('.remove-question-btn')) {
            const button = e.target.closest('.remove-question-btn');
            const questionId = button.getAttribute('data-question-id');
            if (questionId) {
                removeQuestion(questionId);
            }
        }
        
        // Handle add MCQ choice button clicks
        if (e.target.closest('.add-mcq-choice-btn')) {
            const button = e.target.closest('.add-mcq-choice-btn');
            const questionId = button.getAttribute('data-question-id');
            if (questionId) {
                addMCQChoice(questionId);
            }
        }
    });

    // Handle question type changes through event delegation
    document.addEventListener('change', function(e) {
        if (e.target.matches('select[id^="question_type_"]')) {
            handleQuestionTypeChange(e);
        }
    });

    // Modify attachEventListeners to only handle non-dynamic elements
    function attachEventListeners() {
        // Add question button listener (this is a static element)
        const addQuestionBtn = document.getElementById('add-question-btn');
        if (addQuestionBtn) {
            addQuestionBtn.addEventListener('click', addQuestion);
        }
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