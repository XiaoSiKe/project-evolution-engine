const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const {JSDOM} = require("./node/node_modules/jsdom");
const root = path.resolve(process.argv[2]);
const mode = process.argv[3] || "all";
const checks = [];
const definitions = [];

function define(id, kind, body) { definitions.push({id, kind, body}); }
async function boot() {
    const dom = new JSDOM(fs.readFileSync(path.join(root, "index.html"), "utf8"), {
        url: "http://todomvc.example/#/", runScripts: "outside-only", pretendToBeVisual: true
    });
    const w = dom.window;
    for (const link of w.document.querySelectorAll('link[rel="stylesheet"]')) {
        const href = link.getAttribute("href");
        if (!href || /^(https?:)?\/\//.test(href)) continue;
        const file = path.resolve(root, href);
        if (fs.existsSync(file)) {
            const style = w.document.createElement("style");
            style.textContent = fs.readFileSync(file, "utf8");
            w.document.head.appendChild(style);
        }
    }
    for (const script of w.document.querySelectorAll("script[src]")) {
        const src = script.getAttribute("src");
        if (src.includes("node_modules/") || path.basename(src) === "base.js" || /^(https?:)?\/\//.test(src)) continue;
        const file = path.resolve(root, src);
        assert.ok(file.startsWith(root + path.sep), "script must stay in app");
        w.eval(fs.readFileSync(file, "utf8"));
    }
    await new Promise(resolve => w.addEventListener("load", resolve, {once: true}));
    const read = () => {
        let rows;
        new w.app.Store("javascript-es5").findAll(data => { rows = JSON.parse(JSON.stringify(data)); });
        return rows;
    };
    const list = () => Array.from(w.document.querySelectorAll(".todo-list li"));
    const item = title => list().find(li => li.querySelector("label").textContent === title);
    const add = title => {
        const input = w.document.querySelector(".new-todo");
        input.value = title;
        input.dispatchEvent(new w.Event("change", {bubbles: true}));
    };
    const toggle = title => item(title).querySelector(".toggle").click();
    const clear = () => w.document.querySelector(".clear-completed").click();
    const undoButton = () => Array.from(w.document.querySelectorAll("button")).find(
        button => /undo clear completed/i.test(button.textContent || button.getAttribute("aria-label") || "")
    );
    const usable = button => {
        if (!button || button.disabled) return false;
        for (let el = button; el; el = el.parentElement) {
            const style = w.getComputedStyle(el);
            if (el.hidden || style.display === "none" || style.visibility === "hidden") return false;
        }
        return true;
    };
    const undo = () => {
        assert.ok(usable(undoButton()), "Undo must be visible and enabled");
        undoButton().click();
    };
    const edit = (title, replacement) => {
        item(title).querySelector("label").dispatchEvent(new w.MouseEvent("dblclick", {bubbles: true}));
        const field = w.document.querySelector(".edit");
        field.value = replacement;
        field.blur();
    };
    const filter = async value => {
        w.location.hash = "#/" + value;
        await new Promise(resolve => w.setTimeout(resolve, 0));
    };
    return {dom, w, read, list, item, add, toggle, clear, undoButton, usable, undo, edit, filter};
}

define("existing_add_trim_and_escape", "preserved", async app => {
    app.add("  alpha  "); app.add("   "); app.add("<b>literal</b>");
    assert.deepEqual(app.read().map(row => row.title), ["alpha", "<b>literal</b>"]);
    assert.equal(app.item("<b>literal</b>").querySelector("label").innerHTML, "&lt;b&gt;literal&lt;/b&gt;");
});
define("existing_toggle_filter_delete", "preserved", async app => {
    app.add("alpha"); app.add("beta"); app.toggle("alpha");
    await app.filter("active");
    assert.deepEqual(app.list().map(li => li.querySelector("label").textContent), ["beta"]);
    await app.filter("completed");
    assert.deepEqual(app.list().map(li => li.querySelector("label").textContent), ["alpha"]);
    await app.filter("");
    app.item("beta").querySelector(".destroy").click();
    assert.deepEqual(app.read().map(row => row.title), ["alpha"]);
});
define("existing_edit_and_count", "preserved", async app => {
    app.add("alpha"); app.edit("alpha", "updated");
    assert.equal(app.read()[0].title, "updated");
    assert.match(app.w.document.querySelector(".todo-count").textContent, /1 item left/);
});
define("undo_unavailable_initially", "new", async app => {
    assert.ok(app.undoButton(), "New undo control must exist");
    assert.equal(app.usable(app.undoButton()), false);
});
define("restore_ids_order_and_state", "integration", async app => {
    app.add("alpha"); app.add("beta"); app.add("gamma");
    app.toggle("alpha"); app.toggle("gamma");
    const before = app.read();
    app.clear(); app.undo();
    assert.deepEqual(app.read(), before);
    assert.equal(app.usable(app.undoButton()), false, "Undo is single-use");
    assert.match(app.w.document.querySelector(".todo-count").textContent, /1 item left/);
});
define("undo_after_all_items_cleared", "integration", async app => {
    app.add("alpha"); app.toggle("alpha");
    const before = app.read();
    app.clear();
    assert.equal(app.read().length, 0);
    app.undo();
    assert.deepEqual(app.read(), before);
});
define("interleaved_add_edit_and_delete_survive", "integration", async app => {
    app.add("alpha"); app.add("beta"); app.add("gamma"); app.add("delta");
    app.toggle("alpha"); app.toggle("gamma");
    const before = app.read();
    app.clear();
    app.add("epsilon"); app.edit("beta", "beta edited");
    app.item("delta").querySelector(".destroy").click();
    const added = app.read().find(row => row.title === "epsilon");
    app.undo();
    assert.deepEqual(app.read(), [before[0], {...before[1], title: "beta edited"}, before[2], added]);
});
define("new_clear_replaces_previous_history", "new", async app => {
    app.add("alpha"); app.add("beta"); app.toggle("alpha");
    app.clear(); app.toggle("beta"); app.clear(); app.undo();
    assert.deepEqual(app.read().map(row => row.title), ["beta"]);
});
define("empty_clear_retains_history_and_route", "integration", async app => {
    app.add("alpha"); app.add("beta"); app.toggle("alpha");
    await app.filter("active");
    app.clear(); app.clear(); app.undo();
    assert.deepEqual(app.read().map(row => row.title), ["alpha", "beta"]);
    assert.equal(app.w.location.hash, "#/active");
    assert.deepEqual(app.list().map(li => li.querySelector("label").textContent), ["beta"]);
    assert.equal(app.w.localStorage.length, 0, "Do not introduce cross-refresh persistence");
});

(async () => {
    for (const definition of definitions.filter(item => mode === "all" || item.kind === mode)) {
        let app;
        try {
            app = await boot();
            await definition.body(app);
            checks.push({id: definition.id, kind: definition.kind, passed: true});
        } catch (error) {
            checks.push({id: definition.id, kind: definition.kind, passed: false, error: String(error.message || error)});
        } finally {
            if (app) app.dom.window.close();
        }
    }
    console.log(JSON.stringify({checks, passed: checks.filter(c => c.passed).length, total: checks.length}));
    process.exitCode = checks.every(c => c.passed) ? 0 : 1;
})().catch(error => { console.error(error); process.exitCode = 2; });
