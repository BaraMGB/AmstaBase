document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("recipe-form");
    const wrapper = document.getElementById("ingredients-wrapper");
    if (!form || !wrapper) return;

    const editorElement = document.getElementById("editor-container");
    const quill = editorElement && window.Quill ? new Quill(editorElement, {
        theme: "snow",
        placeholder: "Zubereitung eingeben …",
        modules: { toolbar: [["bold", "italic", "underline"], [{list: "ordered"}, {list: "bullet"}], ["link"]] }
    }) : null;

    form.addEventListener("submit", () => {
        if (quill) document.getElementById("hidden-instructions").value = quill.root.innerHTML;
    });

    let ingredientCount = Number.parseInt(wrapper.dataset.count, 10) || 1;
    document.getElementById("add-ingredient-btn")?.addEventListener("click", () => {
        ingredientCount += 1;
        wrapper.insertAdjacentHTML("beforeend", `
            <div class="row g-2 ingredient-set mb-2">
                <div class="col-auto handle"><i class="bi bi-grip-vertical"></i></div>
                <div class="col"><input type="number" step="0.01" name="quantity_${ingredientCount}" placeholder="Menge" class="form-control quantity-input"></div>
                <div class="col"><select name="unit_${ingredientCount}" class="form-control unit-dropdown"><option>g</option><option>ml</option><option>Stück</option><option>nach Geschmack</option></select></div>
                <div class="col"><input name="ingredient_name_${ingredientCount}" placeholder="Zutat" class="form-control"></div>
                <div class="col-auto"><button type="button" class="btn btn-danger btn-sm remove-ingredient">×</button></div>
            </div>`);
        wrapper.lastElementChild.querySelector(".quantity-input").focus();
    });

    wrapper.addEventListener("click", (event) => {
        const button = event.target.closest(".remove-ingredient");
        if (button) button.closest(".ingredient-set").remove();
    });
    wrapper.addEventListener("change", (event) => {
        const row = event.target.closest(".ingredient-set");
        if (!row) return;
        if (event.target.matches(".unit-dropdown") && event.target.value === "nach Geschmack") row.querySelector(".quantity-input").value = 0;
        if (event.target.matches(".quantity-input") && Number(event.target.value) === 0) row.querySelector(".unit-dropdown").value = "nach Geschmack";
    });

    if (window.jQuery?.fn.sortable) window.jQuery(wrapper).sortable({handle: ".handle"});

    document.querySelectorAll(".delete-photo-btn").forEach((button) => {
        button.addEventListener("click", () => {
            const id = button.dataset.photoId;
            document.getElementById(`delete-photo-input-${id}`).value = "1";
            document.getElementById(`photo-${id}`).classList.add("d-none");
        });
    });
});
