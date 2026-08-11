---
title: Home
url: index.html
description: >-
  Global analyses of neutrino oscillation data by the Bari group: best fits and
  allowed ranges for the three-flavour parameters, a daily arXiv digest, news,
  conferences and curated resources.
katex: false
---

<section class="hero hero--split">
  <div class="wrap hero__in">
    <div>
      <p class="kicker"><b>●</b> Release March 2025 · PRD 111, 093006</p>
      <h1>Global analyses of neutrino<br>oscillation data</h1>
      <p class="lede">The Bari global analysis of neutrino oscillation data,
      published openly: best fits, allowed ranges, both mass orderings, and
      files you can compute with.</p>
      <div class="btn-row">
        <a class="btn" href="results.html">Explore the results</a>
        <a class="btn btn--ghost" href="history.html">Parameter history</a>
      </div>
    </div>

    <figure class="figure">
      <h4>Three-flavour oscillation · schematic, not a fit</h4>
      <svg viewBox="0 0 520 230" role="img" aria-label="Schematic oscillation probabilities for the two mass orderings">
        <line x1="42" y1="196" x2="504" y2="196" stroke="currentColor" stroke-width="1" opacity=".35"/>
        <line x1="42" y1="16" x2="42" y2="196" stroke="currentColor" stroke-width="1" opacity=".35"/>
        <line x1="42" y1="150" x2="504" y2="150" stroke="currentColor" stroke-width="1" stroke-dasharray="3 5" opacity=".22"/>
        <line x1="42" y1="100" x2="504" y2="100" stroke="currentColor" stroke-width="1" stroke-dasharray="3 5" opacity=".22"/>
        <line x1="42" y1="50"  x2="504" y2="50"  stroke="currentColor" stroke-width="1" stroke-dasharray="3 5" opacity=".22"/>
        <path d="M60 28 Q 205 246 250 196 Q 300 246 470 20"
              fill="none" stroke="var(--no)" stroke-width="2.4" stroke-linecap="round"/>
        <path d="M70 18 Q 250 232 300 180 Q 350 232 486 32"
              fill="none" stroke="var(--io)" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="7 5"/>
      </svg>
      <div class="legend">
        <span><i class="k-no"></i>normal ordering</span>
        <span><i class="k-io"></i>inverted ordering</span>
      </div>
      <p class="cap">Illustrative. The release’s own Δχ² profiles, drawn from
      the published files, live on the <a href="results.html">results page</a>.</p>
    </figure>
  </div>
</section>

::: section

<div class="section-head">
  <h2>Best fits</h2>
  <p>normal ordering · arXiv:2503.07752</p>
  <a class="more" href="results.html">Full tables and ranges →</a>
</div>

<div class="stats reveal">
  <div class="stat"><span class="k">sin²θ₁₂</span><span class="v">0.303</span><span class="u">1σ accuracy 4.5%</span><!--include:spark-sin2_th12--></div>
  <div class="stat"><span class="k">sin²θ₁₃</span><span class="v">0.0223</span><span class="u">1σ accuracy 2.4%</span><!--include:spark-sin2_th13--></div>
  <div class="stat"><span class="k">sin²θ₂₃</span><span class="v">0.473</span><span class="u">1σ accuracy 5.1%</span><!--include:spark-sin2_th23--></div>
  <div class="stat"><span class="k">δm² / 10⁻⁵ eV²</span><span class="v">7.37</span><span class="u">m₂² − m₁² &gt; 0</span><!--include:spark-dm2--></div>
  <div class="stat"><span class="k">|Δm²| / 10⁻³ eV²</span><span class="v">2.495</span><span class="u">m₃² − (m₁²+m₂²)/2</span><!--include:spark-Dm2--></div>
  <div class="stat"><span class="k">δ/π</span><span class="v">1.20</span><span class="u">CP phase, cyclic mod 2</span><!--include:spark-delta_pi--></div>
</div>

<p class="small muted" style="margin-top:1.1rem">Normal ordering is favoured at
2.2σ; the χ² offset between the orderings is Δχ²(IO−NO) = +5.0. All values from
Table I of <a href="https://doi.org/10.1103/PhysRevD.111.093006">Phys. Rev. D
111, 093006 (2025)</a>, in the conventions stated there.</p>

:::

::: section alt glow

<div class="cards reveal">

<a class="card card--2" href="digest.html">
<span class="card__tag">Updated daily</span>
<h3>Today on arXiv</h3>
<p class="small muted">Experimental and theoretical preprints of the day, kept
in two streams and ranked by a stated keyword score — no model decides what
appears there.</p>
<span class="card__go">The full digest →</span>
</a>

<a class="card card--3" href="news.html">
<span class="card__tag">News</span>
<h3>What is happening</h3>
<p class="small muted">Experiments, results and milestones, written from
fetched sources: every claim on that page carries the link it came from, and
an item whose citation cannot be resolved is dropped before publication.</p>
<span class="card__go">More news →</span>
</a>

<a class="card card--5" href="conferences.html">
<span class="card__tag">Conferences</span>
<h3>Where the field meets</h3>
<p class="small muted">Upcoming and recent meetings with dates, venues and
links, rebuilt each day from the conference indexers rather than kept by
hand.</p>
<span class="card__go">The calendar →</span>
</a>

</div>

:::

::: section

<figure class="figure figure--wide reveal">
<div class="figure__head">
  <h3>A quarter century of sharpening</h3>
  <p>formal 1σ accuracy · logarithmic scale</p>
</div>
<!--include:precision-->
<p class="cap">Each line is one parameter’s formal 1σ accuracy — a sixth of its
3σ range over its best fit — as published in each release. Computed from the
same tables the <a href="history.html">parameter history</a> is built on.</p>
</figure>

:::

::: section alt glow

<div class="strip reveal">
  <a href="history.html"><span class="t">Parameter history</span><span class="d">A quarter century of global fits — Bari, Valencia, NuFit — each point traced to its paper</span></a>
  <a href="results.html#data"><span class="t">Machine-readable data</span><span class="d">Stable URLs and a documented schema, built to be scripted against</span></a>
  <a href="resources.html"><span class="t">Resources</span><span class="d">Experiments, data releases, databases and reviews, in one curated place</span></a>
</div>

:::
