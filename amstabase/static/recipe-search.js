document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("recipe-search-form");
    const input = document.getElementById("recipe-search");
    const clearButton = document.getElementById("recipe-search-clear");
    const resultsContainer = document.getElementById("recipe-results");
    const emptyMessage = document.getElementById("recipe-search-empty");
    const status = document.getElementById("recipe-search-status");
    if (!form || !input || !clearButton || !resultsContainer || !emptyMessage || !status) return;

    const normalize = (value) => value
        .toLocaleLowerCase("de-DE")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/ß/g, "ss")
        .replace(/[^a-z0-9]+/g, " ")
        .trim();

    const editDistance = (left, right) => {
        const matrix = Array.from({length: left.length + 1}, () =>
            Array(right.length + 1).fill(0));
        for (let row = 0; row <= left.length; row += 1) matrix[row][0] = row;
        for (let column = 0; column <= right.length; column += 1) matrix[0][column] = column;

        for (let row = 1; row <= left.length; row += 1) {
            for (let column = 1; column <= right.length; column += 1) {
                const cost = left[row - 1] === right[column - 1] ? 0 : 1;
                matrix[row][column] = Math.min(
                    matrix[row - 1][column] + 1,
                    matrix[row][column - 1] + 1,
                    matrix[row - 1][column - 1] + cost
                );
                if (
                    row > 1 && column > 1
                    && left[row - 1] === right[column - 2]
                    && left[row - 2] === right[column - 1]
                ) {
                    matrix[row][column] = Math.min(
                        matrix[row][column],
                        matrix[row - 2][column - 2] + 1
                    );
                }
            }
        }
        return matrix[left.length][right.length];
    };

    const subsequenceScore = (query, candidate) => {
        let queryIndex = 0;
        let firstMatch = -1;
        let lastMatch = -1;
        for (let index = 0; index < candidate.length && queryIndex < query.length; index += 1) {
            if (candidate[index] === query[queryIndex]) {
                if (firstMatch === -1) firstMatch = index;
                lastMatch = index;
                queryIndex += 1;
            }
        }
        if (queryIndex !== query.length) return Number.POSITIVE_INFINITY;
        return 1 + firstMatch * 0.05 + (lastMatch - firstMatch + 1 - query.length) * 0.08;
    };

    const tokenScore = (query, candidate) => {
        if (query === candidate) return 0;
        if (candidate.startsWith(query)) return 0.1 + (candidate.length - query.length) * 0.01;
        const substringIndex = candidate.indexOf(query);
        if (substringIndex !== -1) return 0.3 + substringIndex * 0.03;

        const distance = editDistance(query, candidate);
        const maxDistance = query.length <= 3 ? 1 : Math.ceil(query.length * 0.35);
        if (distance <= maxDistance) {
            return 0.6 + distance / Math.max(query.length, candidate.length);
        }
        if (query.length >= 2) return subsequenceScore(query, candidate);
        return Number.POSITIVE_INFINITY;
    };

    const fuzzyScore = (query, name, ingredients) => {
        const combined = `${name} ${ingredients}`.trim();
        if (combined.includes(query)) {
            const nameBonus = name.includes(query) ? -0.3 : 0;
            return combined.indexOf(query) * 0.01 + nameBonus;
        }

        const candidateTokens = combined.split(" ").filter(Boolean);
        let score = 0;
        for (const queryToken of query.split(" ").filter(Boolean)) {
            let bestTokenScore = Number.POSITIVE_INFINITY;
            for (const candidateToken of candidateTokens) {
                bestTokenScore = Math.min(
                    bestTokenScore,
                    tokenScore(queryToken, candidateToken)
                );
            }
            if (!Number.isFinite(bestTokenScore)) return Number.POSITIVE_INFINITY;
            score += bestTokenScore;
        }
        return score - (name.split(" ").some((token) => token.startsWith(query)) ? 0.2 : 0);
    };

    const entries = Array.from(resultsContainer.querySelectorAll(".recipe-result")).map(
        (element) => ({
            element,
            link: element.querySelector("a"),
            name: normalize(element.dataset.recipeName || ""),
            displayName: element.dataset.recipeName || "",
            ingredients: normalize(element.dataset.recipeIngredients || ""),
        })
    );
    let visibleEntries = [];
    let activeIndex = -1;

    const selectResult = (index) => {
        if (!visibleEntries.length) {
            activeIndex = -1;
            return;
        }
        activeIndex = (index + visibleEntries.length) % visibleEntries.length;
        for (const entry of entries) {
            const active = entry === visibleEntries[activeIndex];
            entry.element.classList.toggle("fuzzy-active", active);
            if (active) entry.link.setAttribute("aria-current", "true");
            else entry.link.removeAttribute("aria-current");
        }
        visibleEntries[activeIndex].element.scrollIntoView({block: "nearest"});
    };

    const updateResults = () => {
        const query = normalize(input.value);
        const rankedEntries = entries
            .map((entry) => ({
                entry,
                score: query ? fuzzyScore(query, entry.name, entry.ingredients) : 0,
            }))
            .filter((result) => Number.isFinite(result.score))
            .sort((left, right) => left.score - right.score
                || left.entry.displayName.localeCompare(right.entry.displayName, "de"));

        for (const entry of entries) {
            entry.element.hidden = true;
            entry.element.classList.remove("fuzzy-active");
            entry.link.removeAttribute("aria-current");
        }
        for (const result of rankedEntries) {
            result.entry.element.hidden = false;
            resultsContainer.append(result.entry.element);
        }

        visibleEntries = rankedEntries.map((result) => result.entry);
        activeIndex = -1;
        if (query && visibleEntries.length) selectResult(0);

        emptyMessage.classList.toggle("d-none", visibleEntries.length !== 0);
        clearButton.hidden = input.value.length === 0;
        status.textContent = query
            ? `${visibleEntries.length} Treffer für „${input.value.trim()}“`
            : `${visibleEntries.length} Rezepte`;

        const url = new URL(window.location.href);
        if (input.value.trim()) url.searchParams.set("search", input.value.trim());
        else url.searchParams.delete("search");
        window.history.replaceState({}, "", url);
    };

    input.addEventListener("input", updateResults);
    input.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            selectResult(activeIndex + 1);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            selectResult(activeIndex <= 0 ? visibleEntries.length - 1 : activeIndex - 1);
        } else if (event.key === "Enter" && activeIndex >= 0) {
            event.preventDefault();
            visibleEntries[activeIndex].link.click();
        } else if (event.key === "Escape") {
            event.preventDefault();
            input.value = "";
            updateResults();
        }
    });
    clearButton.addEventListener("click", () => {
        input.value = "";
        updateResults();
        input.focus();
    });
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        if (visibleEntries.length) visibleEntries[Math.max(activeIndex, 0)].link.click();
    });
    document.addEventListener("keydown", (event) => {
        const target = event.target;
        const typing = target instanceof HTMLInputElement
            || target instanceof HTMLTextAreaElement
            || target.isContentEditable;
        if (event.key === "/" && !typing) {
            event.preventDefault();
            input.focus();
        }
    });

    updateResults();
});
