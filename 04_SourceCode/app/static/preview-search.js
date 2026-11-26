const search = document.getElementById("member-search");
const rows = Array.from(document.querySelectorAll("[data-search-row]"));
const empty = document.getElementById("member-search-empty");

search.addEventListener("input", () => {
  const query = search.value.trim().toLocaleLowerCase("vi");
  for (const row of rows) {
    row.hidden = !row.dataset.searchText.toLocaleLowerCase("vi").includes(query);
  }
  empty.hidden = rows.some((row) => !row.hidden);
});
