/**
 * Compute Mastery — CodeMirror 6 Editor Setup
 * Loaded as ES module in problem_detail.html
 */
import {EditorView, basicSetup} from "https://esm.sh/codemirror@6.0.1";
import {cpp} from "https://esm.sh/@codemirror/lang-cpp@6.0.2";
import {oneDark} from "https://esm.sh/@codemirror/theme-one-dark@6.1.2";
import {keymap} from "https://esm.sh/@codemirror/view@6.35.0";
import {indentWithTab} from "https://esm.sh/@codemirror/commands@6.7.1";

const editorContainer = document.getElementById('code-editor');
if (!editorContainer) throw new Error('Editor container not found');

const config = window.MASTERY_CONFIG || {};

// Create CodeMirror editor
const editor = new EditorView({
    doc: config.initialCode || '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}',
    extensions: [
        basicSetup,
        cpp(),
        oneDark,
        keymap.of([indentWithTab]),
        EditorView.theme({
            '&': {
                fontSize: '0.85rem',
                minHeight: '400px',
                maxHeight: '600px',
            },
            '.cm-scroller': {
                overflow: 'auto',
                fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
            },
        }),
    ],
    parent: editorContainer,
});

// Expose editor to global scope for results.js
window.masteryEditor = editor;
