---
title: Search
url: search.html
description: >-
  A free-form search across INSPIRE-HEP, arXiv, Crossref and OpenAlex. Type an
  author, a title, a topic and a date range in plain language; the correct query
  is built for each database and the results are shown here.
katex: false
scripts:
  - assets/js/search.js
---

<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Tools</p>
    <h1>Literature <i class="grad">search</i></h1>
    <p class="lede">Type a query the way you would say it — an author, a few
    words of the title, a topic, a year or a range. The right query is built for
    each database and the results appear below, on this page.</p>
  </div>
</section>

::: section

<form id="lit-form" class="lit" autocomplete="off">

  <div class="lit__main">
    <label class="lit__label" for="q-free">Your query</label>
    <input id="q-free" class="lit__free" type="search" name="q"
           placeholder="e.g. Lisi Marrone modular symmetry 2023-2025"
           aria-describedby="lit-chips">
  </div>

  <p class="lit__hint">Recognised automatically: surnames, quoted titles,
  experiment names, arXiv identifiers, and dates written as
  <code>2019-2023</code>, <code>2019-&gt;2023</code>, <code>since 2020</code>, <code>before 2015</code>,
  <code>last 3 years</code>, <code>March 2024</code>. You can also be explicit
  with <code>a:Lisi</code>, <code>t:"neutrino masses"</code>, and
  <code>c:T2K</code> for papers <em>signed by</em> a collaboration rather than
  about it.</p>

  <div id="lit-chips" class="lit__chips" aria-live="polite"></div>

  <details class="acc lit__acc">
    <summary>Refine the interpreted fields</summary>
    <div class="acc__body">
      <div class="lit__grid">
        <div>
          <label class="lit__label" for="q-author">Author(s)</label>
          <input id="q-author" type="text" placeholder="Lisi; Marrone">
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
        <div>
          <label class="lit__label" for="q-from">From</label>
          <input id="q-from" type="text" inputmode="numeric" placeholder="2019">
        </div>
        <div>
          <label class="lit__label" for="q-to">To</label>
          <input id="q-to" type="text" inputmode="numeric" placeholder="2025">
        </div>
        <div>
          <label class="lit__label" for="q-sort">Sort by</label>
          <select id="q-sort">
            <option value="date" selected>Most recent first</option>
            <option value="relevance">Relevance / citations</option>
          </select>
        </div>
      </div>
    </div>
  </details>

  <fieldset class="lit__sources">
    <legend class="lit__label">Search in</legend>
    <label class="lit__check"><input type="checkbox" id="src-inspire" checked> INSPIRE-HEP</label>
    <label class="lit__check"><input type="checkbox" id="src-crossref" checked> Crossref</label>
    <label class="lit__check"><input type="checkbox" id="src-openalex"> OpenAlex</label>
    <label class="lit__check"><input type="checkbox" id="src-arxiv" checked> arXiv</label>
  </fieldset>

  <div class="btn-row">
    <button class="btn btn--solid" type="submit">Search</button>
    <button class="btn btn--ghost" type="button" id="lit-clear">Clear</button>
  </div>

</form>

<p class="lit__label" style="margin-top:2rem">Also open this query in</p>
<div id="lit-outbound" class="btn-row"></div>

<p class="lit__hint">Try:
  <a href="#" data-example='Lisi Marrone modular symmetry 2023-2025'>Lisi Marrone modular symmetry 2023-2025</a> ·
  <a href="#" data-example='t:"neutrinoless double beta decay" since 2022'>neutrinoless double beta decay since 2022</a> ·
  <a href="#" data-example='T2K oscillation last 2 years'>T2K oscillation last 2 years</a> ·
  <a href="#" data-example='Feruglio modular forms flavour'>Feruglio modular forms flavour</a>
</p>

:::

::: section alt #lit-pane

<p id="lit-status" class="lit__status" aria-live="polite"></p>
<div id="lit-results" class="lit__results"></div>

:::

::: section

<div class="section-head">
  <h2>How it works</h2>
</div>

::: prose

The query you type is parsed in your browser into structured fields — author,
title, topic, collaboration, date range — which are shown as chips so you can see
exactly how the sentence was understood, and corrected by hand if the guess was
wrong. Each database then receives a query in its own syntax: INSPIRE's
`a Lisi and t "modular" and de 2023->2025`, Crossref's `query.author` with
`from-pub-date` filters, OpenAlex's `filter=` expressions.

Everything happens in your browser. This site runs no server-side code, so the
requests go directly from you to the databases: nothing you type is sent to,
logged by, or stored on `global-nu.org`.

**How arXiv is reached.** A browser may read a remote API only if that API sends
the appropriate CORS header, and `export.arxiv.org` does not — a direct call
from this page would be refused by the browser before you saw anything. But
arXiv registers a DOI for every preprint with DataCite, under the
`10.48550/arXiv.*` prefix, and DataCite's API does send CORS and needs no key.
So the arXiv results here are arXiv's own metadata, deposited by arXiv, fetched
from the one place a browser is allowed to read it.

**Why not NASA ADS.** It requires a personal token, which would have to be
published in the page source to work — so for ADS the parsed query is turned
into a correct search URL and offered as a button instead.

Results are capped at 20 per database, and every outbound link opens in a new
tab, so you never lose your place here.

:::

:::
