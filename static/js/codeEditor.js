// Code Editor Configuration
class CodeEditorManager {
    constructor() {
        this.editors = new Map();
        this.languageModes = {
            'python': {
                mode: {
                    name: 'python',
                    version: 3
                },
                name: 'Python'
            },
            'javascript': {
                mode: {
                    name: 'javascript',
                    json: true
                },
                name: 'JavaScript'
            },
            'php': {
                mode: {
                    name: 'php',
                    startOpen: true
                },
                name: 'PHP'
            },
            'sql': {
                mode: {
                    name: 'sql',
                    dialect: 'mysql'
                },
                name: 'MySQL'
            }
        };
    }

    initializeEditor(textarea) {
        if (!textarea || this.editors.has(textarea.id)) return;

        const wrapper = textarea.closest('.code-question-wrapper');
        if (!wrapper) return;

        const languageSelector = wrapper.querySelector('.language-selector');
        const selectedMode = this.languageModes[languageSelector ? .value || 'python'];

        const editorOptions = {
            lineNumbers: true,
            mode: selectedMode ? .mode || {
                name: 'python',
                version: 3
            },
            theme: document.documentElement.classList.contains('dark') ? 'monokai' : 'eclipse',
            indentUnit: 4,
            tabSize: 4,
            lineWrapping: true,
            matchBrackets: true,
            autoCloseBrackets: true,
            extraKeys: {
                "Tab": cm => cm.replaceSelection("    ", "end")
            }
        };

        const editor = CodeMirror.fromTextArea(textarea, editorOptions);
        this.editors.set(textarea.id, editor);
        this.setupLanguageSelector(wrapper, editor);
        this.setupThemeObserver(editor);
        this.setupChangeHandler(textarea, editor);

        return editor;
    }

    setupLanguageSelector(wrapper, editor) {
        const languageSelector = wrapper.querySelector('.language-selector');
        if (!languageSelector) return;

        languageSelector.addEventListener('change', () => {
            const selectedMode = this.languageModes[languageSelector.value];
            if (!selectedMode) return;
            editor.setOption('mode', selectedMode.mode);
        });
    }

    setupThemeObserver(editor) {
        const observer = new MutationObserver(mutations => {
            mutations.forEach(mutation => {
                if (mutation.attributeName === 'class') {
                    const isDark = document.documentElement.classList.contains('dark');
                    editor.setOption('theme', isDark ? 'monokai' : 'eclipse');
                }
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['class']
        });
    }

    setupChangeHandler(textarea, editor) {
        editor.on('change', () => {
            // Update textarea value
            editor.save();

            // If there's an existing exam logging system, integrate with it
            if (typeof window.logExamAction === 'function') {
                window.logExamAction('code_edit', {
                    question_id: textarea.name.replace('question_', ''),
                    content_length: editor.getValue().length
                });
            }
        });
    }

    // Method to get editor instance
    getEditor(textareaId) {
        return this.editors.get(textareaId);
    }

    // Method to update all editors' values (useful when restoring saved answers)
    updateEditorValue(textareaId, value) {
        const editor = this.getEditor(textareaId);
        if (editor) {
            editor.setValue(value || '');
        }
    }

    // Initialize all code editors on the page
    initializeAll() {
        document.querySelectorAll('.code-editor').forEach(textarea => {
            if (!textarea.id) {
                textarea.id = 'code-editor-' + Math.random().toString(36).substr(2, 9);
            }
            this.initializeEditor(textarea);
        });
    }
}

// Export for global use
window.CodeEditorManager = CodeEditorManager;