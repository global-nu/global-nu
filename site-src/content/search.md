---
title: Search
head_title: "Neutrino literature search: INSPIRE, arXiv — global-nu"
url: search.html
description: >-
  A free-form physics literature search across INSPIRE-HEP, arXiv, Semantic
  Scholar, Crossref and OpenAlex. Type an author, a title, a topic and a date
  range in plain language; the right query is built for each database and the
  results are shown here.
katex: false
scripts:
  - assets/js/search.js
---

<section class="hero hero--compact">
  <div class="wrap hero__in">
    <p class="kicker">Tools</p>
    <h1>Literature search</h1>
    <p class="lede">Type a query the way you would say it — an author, a few
    words of the title, a topic, a year or a range. The right query is built for
    each database and the results appear below, on this page.</p>
  </div>
</section>

::: section

<link rel="stylesheet" href="assets/css/search.css">

<form id="lit-form" class="lit" autocomplete="off">

  <div class="lit__main">
    <label class="lit__label" for="q-free">Your query</label>
    <input id="q-free" class="lit__free" type="search" name="q"
           placeholder="e.g. JUNO reactor oscillation 2025"
           aria-describedby="lit-chips">
  </div>

  <div id="lit-chips" class="lit__chips" aria-live="polite"></div>

  <div class="lit__bar">
    <button class="btn btn--solid lit__go" type="submit">Search</button>
    <div id="lit-mode" class="lit-seg" role="group" aria-label="How strictly records must match">
      <button type="button" class="lit-seg__btn" data-mode="precise" aria-pressed="true"
              title="Every record must contain your terms in its title, abstract or keywords">Precise</button>
      <button type="button" class="lit-seg__btn" data-mode="broad" aria-pressed="false"
              title="Trust the databases' own ranking; only generic ones are checked">Broad</button>
    </div>
  </div>

  <details id="lit-adv" class="acc lit__adv">
    <summary>Advanced options</summary>
    <div class="acc__body">

      <p class="lit__hint">Recognised automatically: surnames, quoted titles,
      experiment names, arXiv identifiers, and dates written as
      <code>2019-2023</code>, <code>2019-&gt;2023</code>, <code>since 2020</code>, <code>before 2015</code>,
      <code>last 3 years</code>, <code>March 2024</code>. You can also be explicit
      with <code>a:Smith</code>, <code>t:"neutrino masses"</code>, and
      <code>c:T2K</code> for papers <em>signed by</em> a collaboration rather than
      about it.</p>

      <p class="lit__hint">The results can be re-ordered — by relevance,
      publication date, citations or subfield, each of them reversible — and
      narrowed to the subfields you want, with the buttons above them. Choosing
      the order before you search is worth it for the date: the databases are then
      asked for their most recent records, which changes which ones come back.
      <em>Precise</em> keeps only records that show your words in their title,
      abstract or keywords; <em>Broad</em> also keeps what the databases rank
      high on weaker evidence.</p>

      <h2 class="lit__sub">Refine the interpreted fields</h2>
      <div class="lit__grid">
        <div>
          <label class="lit__label" for="q-author">Author(s)</label>
          <input id="q-author" type="text" placeholder="Surname; Surname">
          <span class="lit__note">Separate several with a semicolon.</span>
        </div>
        <div>
          <label class="lit__label" for="q-title">Title contains</label>
          <input id="q-title" type="text" placeholder="neutrino masses and mixing">
        </div>
        <div>
          <label class="lit__label" for="q-topic">Topic / keywords</label>
          <input id="q-topic" type="text" placeholder="seesaw leptogenesis">
        </div>
        <div>
          <label class="lit__label" for="q-collab">Signed by collaboration</label>
          <input id="q-collab" type="text" placeholder="T2K">
          <span class="lit__note">Membership, not subject. An experiment name
          typed in the box above is treated as a topic instead — use
          <code>c:T2K</code> to force this field.</span>
        </div>
      </div>

      <h2 class="lit__sub">Time and discipline</h2>
      <div class="lit__grid">
        <div>
          <label class="lit__label" for="adv-time">Published</label>
          <select id="adv-time">
            <option value="any" selected>Any time</option>
            <option value="1">Last year</option>
            <option value="2">Last 2 years</option>
            <option value="5">Last 5 years</option>
            <option value="custom">Custom range</option>
          </select>
        </div>
        <div>
          <label class="lit__label" for="q-from">From</label>
          <input id="q-from" type="text" inputmode="numeric" placeholder="2019">
        </div>
        <div>
          <label class="lit__label" for="q-to">To</label>
          <input id="q-to" type="text" inputmode="numeric" placeholder="2025">
        </div>
        <div>
          <label class="lit__label" for="adv-disc">Discipline</label>
          <select id="adv-disc">
            <option value="all" selected>All physics</option>
            <option value="neutrino">Neutrino physics</option>
          </select>
          <span class="lit__note">Decided from the title and venue, as the subfield labels are.</span>
        </div>
      </div>

      <fieldset class="lit__sources">
        <legend class="lit__label">Search in</legend>
        <label class="lit__check"><input type="checkbox" id="src-inspire" checked> INSPIRE-HEP</label>
        <label class="lit__check"><input type="checkbox" id="src-crossref" checked> Crossref</label>
        <label class="lit__check"><input type="checkbox" id="src-openalex" checked> OpenAlex</label>
        <label class="lit__check"><input type="checkbox" id="src-arxiv" checked> arXiv</label>
        <label class="lit__check"><input type="checkbox" id="src-s2" checked> Semantic Scholar</label>
      </fieldset>
      <p class="lit__note">Results are filtered to physics: OpenAlex is asked for
      Physical Sciences only, Semantic Scholar for Physics, and a record found
      only by the generic databases must actually contain your query terms.
      Google Scholar has no public search API, and NASA ADS's requires a personal
      token — use the buttons under the results to open the same query there.</p>

      <div class="btn-row">
        <button class="btn btn--ghost" type="button" id="lit-clear">Clear</button>
      </div>
    </div>
  </details>

</form>

<p class="lit__hint" id="lit-try">Try:
  <a href="#" data-example='JUNO reactor oscillation 2025'>JUNO reactor oscillation 2025</a> ·
  <a href="#" data-example='t:"neutrinoless double beta decay" since 2022'>neutrinoless double beta decay</a> ·
  <a href="#" data-example='T2K oscillation last 2 years'>T2K oscillation</a>
</p>

:::

::: section alt #lit-pane

<p id="lit-status" class="lit__status" aria-live="polite"></p>
<div id="lit-badges" class="lit-badges" hidden></div>
<div id="lit-sort" class="lit-sort" role="group" aria-label="Order the results" hidden></div>
<div id="lit-filters" class="lit-sort lit-sort--filters" role="group" aria-label="Show only some subfields" hidden></div>
<div id="lit-results" class="lit__results"></div>

:::

::: section

<p class="lit__label">Also open this query in</p>
<div id="lit-outbound" class="btn-row"></div>

:::

::: section

<div class="section-head">
  <h2>How it works</h2>
</div>

<ul class="howto">
<li>Your query is read <b>in your browser</b> into author, title, topic, collaboration and dates, shown as chips you can correct.</li>
<li>Each database — INSPIRE-HEP, arXiv, Crossref, OpenAlex, Semantic Scholar — gets it in its own syntax, <b>directly from you</b>: nothing passes through this site.</li>
<li><b>Precise</b> (default) keeps a record only if its title, abstract, keywords or collaboration contain your words; an experiment name such as JUNO, DUNE or NOvA also needs a neutrino context. <b>Broad</b> keeps weaker matches.</li>
<li>Ranking is by how well a record matches your query; citations only break ties, and the counts come from INSPIRE alone.</li>
<li>If INSPIRE finds nothing, the constraints are relaxed one at a time, and the status line says which one went.</li>
<li>A database that does not answer is marked with a badge; the others' results still appear.</li>
<li>NASA ADS and Google Scholar have no open search API: the buttons above open the same query there.</li>
</ul>

:::
