(() => {
    const insertWrapped = (textarea, prefix, suffix, placeholder) => {
        const start = textarea.selectionStart ?? 0;
        const end = textarea.selectionEnd ?? 0;
        const value = textarea.value;
        const selected = value.slice(start, end);
        const content = selected || placeholder;
        const next = `${value.slice(0, start)}${prefix}${content}${suffix}${value.slice(end)}`;
        textarea.value = next;
        const cursorStart = start + prefix.length;
        const cursorEnd = cursorStart + content.length;
        textarea.setSelectionRange(cursorStart, cursorEnd);
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
    };

    const prefixLines = (textarea, prefix, placeholder) => {
        const start = textarea.selectionStart ?? 0;
        const end = textarea.selectionEnd ?? 0;
        const value = textarea.value;
        const selected = value.slice(start, end) || placeholder;
        const withPrefix = selected
            .split("\n")
            .map((line) => `${prefix}${line}`)
            .join("\n");
        const next = `${value.slice(0, start)}${withPrefix}${value.slice(end)}`;
        textarea.value = next;
        textarea.setSelectionRange(start, start + withPrefix.length);
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
    };

    const runAction = (textarea, action) => {
        switch (action) {
            case "bold":
                insertWrapped(textarea, "**", "**", "important point");
                break;
            case "italic":
                insertWrapped(textarea, "_", "_", "context");
                break;
            case "bullet":
                prefixLines(textarea, "- ", "First point");
                break;
            case "quote":
                prefixLines(textarea, "> ", "Reference note");
                break;
            case "link":
                insertWrapped(textarea, "[", "](https://example.org)", "source");
                break;
            default:
                break;
        }
    };

    const onToolbarClick = (event) => {
        const button = event.target.closest("[data-editor-action]");
        if (!button) {
            return;
        }
        const toolbar = button.closest("[data-editor-toolbar]");
        if (!toolbar) {
            return;
        }
        const targetId = toolbar.getAttribute("data-target");
        if (!targetId) {
            return;
        }
        const textarea = document.getElementById(targetId);
        if (!(textarea instanceof HTMLTextAreaElement)) {
            return;
        }
        event.preventDefault();
        runAction(textarea, button.getAttribute("data-editor-action"));
        textarea.focus();
    };

    document.addEventListener("click", onToolbarClick);
})();
