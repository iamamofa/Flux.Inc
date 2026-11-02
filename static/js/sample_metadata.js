(function () {
    'use strict';
    const initialized = new WeakSet();
    let nextField = 0;
    function message(editor, text) {
        const output = editor.querySelector('[data-metadata-error]');
        output.textContent = text;
        output.hidden = !text;
    }
    function updateEmpty(editor) {
        const count = editor.querySelectorAll('[data-metadata-row]').length;
        editor.querySelector('[data-metadata-empty]').hidden = count > 0;
        editor.querySelector('[data-metadata-add]').disabled = count >= 50;
    }
    function addRow(editor, key = '', value = '', focus = false) {
        if (editor.querySelectorAll('[data-metadata-row]').length >= 50) return;
        const row = document.createElement('div');
        row.className = 'sample-metadata-row';
        row.dataset.metadataRow = '';
        const suffix = ++nextField;
        const keyLabel = document.createElement('label');
        keyLabel.textContent = 'Field name';
        const keyInput = document.createElement('input');
        keyInput.type = 'text';
        keyInput.id = 'metadata-key-' + suffix;
        keyInput.maxLength = 80;
        keyInput.placeholder = 'e.g. Study ID';
        keyInput.setAttribute('list', 'sampleMetadataFieldNames');
        keyInput.dataset.metadataKey = '';
        keyInput.value = key;
        keyLabel.htmlFor = keyInput.id;
        keyLabel.appendChild(keyInput);
        const valueLabel = document.createElement('label');
        valueLabel.textContent = 'Value';
        const valueInput = document.createElement('textarea');
        valueInput.id = 'metadata-value-' + suffix;
        valueInput.rows = 2;
        valueInput.maxLength = 2000;
        valueInput.placeholder = 'Enter a value';
        valueInput.dataset.metadataValue = '';
        valueInput.value = value;
        valueLabel.htmlFor = valueInput.id;
        valueLabel.appendChild(valueInput);
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'sample-metadata-remove';
        remove.textContent = 'Remove';
        remove.setAttribute('aria-label', 'Remove metadata field ' + (key || suffix));
        remove.addEventListener('click', function () {
            row.remove();
            updateEmpty(editor);
            message(editor, '');
            editor.querySelector('[data-metadata-add]').focus();
        });
        row.append(keyLabel, valueLabel, remove);
        editor.querySelector('[data-metadata-rows]').appendChild(row);
        updateEmpty(editor);
        if (focus) keyInput.focus();
    }
    function initialize(editor) {
        if (initialized.has(editor)) return;
        initialized.add(editor);
        editor.querySelector('[data-metadata-add]').addEventListener('click', function () {
            addRow(editor, '', '', true);
        });
        updateEmpty(editor);
    }
    function populate(form, metadata) {
        const editor = form?.querySelector('[data-sample-metadata-editor]');
        if (!editor) return;
        initialize(editor);
        editor.querySelector('[data-metadata-rows]').replaceChildren();
        editor.querySelector('[name="metadata"]').value = JSON.stringify(metadata || {});
        Object.entries(metadata || {}).forEach(function ([key, value]) { addRow(editor, key, value); });
        message(editor, '');
        updateEmpty(editor);
    }
    function serialize(form) {
        const editor = form?.querySelector('[data-sample-metadata-editor]');
        if (!editor) return;
        const values = Object.create(null);
        const names = new Set();
        message(editor, '');
        for (const row of editor.querySelectorAll('[data-metadata-row]')) {
            const keyInput = row.querySelector('[data-metadata-key]');
            const valueInput = row.querySelector('[data-metadata-value]');
            const key = keyInput.value.trim();
            const value = valueInput.value;
            if (!key && !value.trim()) continue;
            let error = '';
            if (!key) error = 'Give each metadata field a name.';
            else if (key.length > 80) error = 'Field names must be 80 characters or fewer.';
            else if (value.length > 2000) error = 'Metadata values must be 2,000 characters or fewer.';
            else if (names.has(key.toLocaleLowerCase())) error = 'Use a different name for each metadata field.';
            if (error) {
                message(editor, error);
                (value.length > 2000 ? valueInput : keyInput).focus();
                throw new Error(error);
            }
            names.add(key.toLocaleLowerCase());
            values[key] = value;
        }
        editor.querySelector('[name="metadata"]').value = JSON.stringify(values);
        return values;
    }
    document.querySelectorAll('[data-sample-metadata-editor]').forEach(initialize);
    document.getElementById('sample-form')?.addEventListener('reset', function () { populate(this, {}); });
    window.SampleMetadata = {populate, serialize};
    const dialog = document.getElementById('sampleMetadataDialog');
    if (!dialog) return;
    const form = dialog.querySelector('form');
    const status = dialog.querySelector('[data-metadata-status]');
    const body = dialog.querySelector('[data-metadata-body]');
    const save = dialog.querySelector('[data-metadata-save]');
    const readOnly = dialog.querySelector('[data-metadata-readonly]');
    let endpoint = '';
    let requestNumber = 0;
    let saving = false;
    function renderReadOnly(metadata) {
        if (!readOnly) return;
        readOnly.replaceChildren();
        if (!Object.keys(metadata).length) {
            const empty = document.createElement('p');
            empty.className = 'sample-metadata-empty';
            empty.textContent = 'No custom metadata has been recorded for this sample.';
            readOnly.appendChild(empty);
            return;
        }
        const list = document.createElement('dl');
        list.className = 'sample-metadata-details';
        Object.entries(metadata).forEach(function ([key, value]) {
            const pair = document.createElement('div');
            const label = document.createElement('dt');
            const content = document.createElement('dd');
            label.textContent = key;
            content.textContent = value || '—';
            pair.append(label, content);
            list.appendChild(pair);
        });
        readOnly.appendChild(list);
    }
    document.addEventListener('click', async function (event) {
        const opener = event.target.closest('[data-sample-metadata-open]');
        if (!opener) return;
        endpoint = opener.dataset.metadataUrl;
        const currentRequest = ++requestNumber;
        dialog.querySelector('[data-metadata-sample]').textContent = opener.dataset.sampleName;
        body.hidden = true;
        status.textContent = 'Loading metadata…';
        status.classList.remove('sample-metadata-error');
        if (save) save.disabled = true;
        dialog.showModal();
        try {
            const response = await fetch(endpoint, {headers: {'Accept': 'application/json'}});
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Could not load sample metadata.');
            if (currentRequest !== requestNumber || !dialog.open) return;
            populate(form, data.metadata || {});
            renderReadOnly(data.metadata || {});
            body.hidden = false;
            status.textContent = '';
            if (save) save.disabled = false;
        } catch (error) {
            if (currentRequest !== requestNumber || !dialog.open) return;
            status.textContent = error.message;
            status.classList.add('sample-metadata-error');
        }
    });
    dialog.querySelectorAll('[data-metadata-close]').forEach(function (button) {
        button.addEventListener('click', function () { if (!saving) dialog.close(); });
    });
    dialog.addEventListener('close', function () { requestNumber++; });
    dialog.addEventListener('cancel', function (event) { if (saving) event.preventDefault(); });
    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        if (!save || saving || save.disabled) return;
        try { serialize(form); } catch (error) { return; }
        saving = true;
        save.disabled = true;
        save.textContent = 'Saving…';
        status.textContent = '';
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value, 'Accept': 'application/json'},
                body: new FormData(form)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Could not save sample metadata.');
            status.textContent = 'Metadata saved.';
            window.location.reload();
        } catch (error) {
            status.textContent = error.message;
            status.classList.add('sample-metadata-error');
            save.disabled = false;
            save.textContent = 'Save metadata';
        } finally { saving = false; }
    });
}());
