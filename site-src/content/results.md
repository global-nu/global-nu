---
title: Results
url: results.html
description: >-
  Results of the Bari global analyses of neutrino oscillation data — best-fit
  values, allowed ranges at 1σ, 2σ and 3σ, for both mass orderings, from the
  most recent full release.
katex: false
---

<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">Results</p>
    <h1>Results, release by release</h1>
    <p class="lede">The most recent full release in detail: best-fit values and
    allowed ranges for the six oscillation parameters, in both mass orderings,
    with the paper and its figures beside them. Every earlier release is traced
    parameter by parameter on the <a href="history.html">parameter
    history</a>.</p>
  </div>
</section>

::: section

<div class="callout">
<h4>Conventions used throughout this site</h4>
<p>The two squared mass gaps are δm² = m₂² − m₁² &gt; 0 and
Δm² = m₃² − ½(m₁² + m₂²), with α = sign(Δm²) distinguishing normal ordering
(NO, α = +1) from inverted ordering (IO, α = −1). Equivalently, our Δm² is the
<strong>half-sum</strong> of the two larger splittings, Δm² = ½(Δm²₃₁ + Δm²₃₂),
which is the form the conversion is easiest to read from: since
Δm²₃₁ − Δm²₃₂ = δm², passing to either of them is a shift of ±δm²/2.</p>
<p>Other groups quote Δm²₃₁ or Δm²₂₃ instead: <strong>those numbers are not
comparable with ours at a glance.</strong> Wherever this site compares
analyses, it states the conversion it applied.</p>
<p><strong>And the errors move differently from the values.</strong> Because
the offset carries its own uncertainty, the converted interval is wider than
the published one: the central value moves by more than one standard deviation
while the uncertainty grows by a fraction of a percent. Both numbers are computed from the register and quoted on the
<a href="history.html#compare">parameter-history page</a>, which also records
that the propagation still omits the δm²–Δm² correlation, and gives the formula — the published
papers do not carry the joint information a rigorous reprojection would need.
The <a href="history.html#data">exported register</a> carries every interval in
both conventions, and an <code>interval_method</code> column saying which
treatment produced it.</p>
</div>

:::

::: section alt glow #nu2025

<div class="release">

<div class="section-head">
  <h2>March 2025 — Entering the era of subpercent precision</h2>
</div>

<p class="lede" style="margin-top:0">Updated global analysis of the known and
unknown parameters of the standard three-neutrino framework, using data
available at the beginning of 2025: solar, KamLAND, atmospheric, short-baseline
reactor and long-baseline accelerator data.</p>

<div class="btn-row">
  <a class="btn btn--sm" href="https://arxiv.org/abs/2503.07752">arXiv:2503.07752</a>
  <a class="btn btn--sm btn--ghost" href="https://doi.org/10.1103/PhysRevD.111.093006">Phys. Rev. D 111, 093006</a>
  <a class="btn btn--sm btn--ghost" href="https://inspirehep.net/literature?q=arxiv:2503.07752">INSPIRE</a>
</div>

<p class="authors"><strong>F. Capozzi, W. Giarè, E. Lisi, A. Marrone,
A. Melchiorri, A. Palazzo.</strong> Received 12 March 2025; accepted 21 April
2025; published 19 May 2025.</p>

<div class="release__meta">
  <span class="tag">both orderings</span>
  <span class="tag">1σ · 2σ · 3σ ranges</span>
  <span class="tag">NO favoured at 2.2σ</span>
  <span class="tag">Δχ²(IO−NO) = +5.0</span>
</div>

<div class="table-scroll">
<table class="data">
<caption>Table I of Phys. Rev. D 111, 093006 (2025): best-fit values and allowed
ranges at N&#8202;σ = 1, 2, 3, for either NO or IO. The last column is the formal
“1σ parameter accuracy”, defined as 1/6 of the 3σ range divided by the best-fit
value, in percent. δ/π is cyclic (mod 2). Values are transcribed from the
published table; nothing on this page is estimated or rounded further.</caption>
<thead>
<tr><th scope="col">Parameter</th><th scope="col">Ordering</th><th scope="col">Best fit</th><th scope="col"><span class="sym">1σ</span> range</th><th scope="col"><span class="sym">2σ</span> range</th><th scope="col"><span class="sym">3σ</span> range</th><th scope="col">“<span class="sym">1σ</span>” (%)</th></tr>
</thead>
<tbody>
<tr><th scope="row">δm² / 10⁻⁵ eV²</th><td class="ord">NO, IO</td><td>7.37</td><td>7.21 – 7.52</td><td>7.06 – 7.71</td><td>6.93 – 7.93</td><td>2.3</td></tr>
<tr><th scope="row">sin²θ₁₂ / 10⁻¹</th><td class="ord">NO, IO</td><td>3.03</td><td>2.91 – 3.17</td><td>2.77 – 3.31</td><td>2.64 – 3.45</td><td>4.5</td></tr>
<tr class="row-alt"><th scope="row">|Δm²| / 10⁻³ eV²</th><td class="ord ord--no">NO</td><td>2.495</td><td>2.475 – 2.515</td><td>2.454 – 2.536</td><td>2.433 – 2.558</td><td>0.8</td></tr>
<tr class="row-alt"><th scope="row"></th><td class="ord ord--io">IO</td><td>2.465</td><td>2.444 – 2.485</td><td>2.423 – 2.506</td><td>2.403 – 2.527</td><td>0.8</td></tr>
<tr><th scope="row">sin²θ₁₃ / 10⁻²</th><td class="ord ord--no">NO</td><td>2.23</td><td>2.17 – 2.27</td><td>2.11 – 2.33</td><td>2.06 – 2.38</td><td>2.4</td></tr>
<tr><th scope="row"></th><td class="ord ord--io">IO</td><td>2.23</td><td>2.19 – 2.30</td><td>2.14 – 2.35</td><td>2.08 – 2.41</td><td>2.4</td></tr>
<tr class="row-alt"><th scope="row">sin²θ₂₃ / 10⁻¹</th><td class="ord ord--no">NO</td><td>4.73</td><td>4.60 – 4.96</td><td>4.47 – 5.68</td><td>4.37 – 5.81</td><td>5.1</td></tr>
<tr class="row-alt"><th scope="row"></th><td class="ord ord--io">IO</td><td>5.45</td><td>5.28 – 5.60</td><td>4.58 – 5.73</td><td>4.43 – 5.83</td><td>4.3</td></tr>
<tr><th scope="row">δ/π</th><td class="ord ord--no">NO</td><td>1.20</td><td>1.07 – 1.37</td><td>0.88 – 1.81</td><td>0.73 – 2.03</td><td>18</td></tr>
<tr><th scope="row"></th><td class="ord ord--io">IO</td><td>1.48</td><td>1.36 – 1.61</td><td>1.24 – 1.72</td><td>1.12 – 1.83</td><td>8</td></tr>
</tbody>
</table>
</div>

<figure class="figure figure--wide reveal" style="margin-top:2rem">
<div class="figure__head">
  <h3>Δχ² projections, all data included</h3>
  <p>Fig. 3 of the paper · NO in blue, IO in red</p>
</div>
<img src="images/prd111-093006-fig3-global-projections.png" alt="Six panels
showing Nσ as a function of δm², |Δm²|, δ/π, sin²θ₁₂, sin²θ₁₃ and sin²θ₂₃, for
normal and inverted ordering, with all oscillation data included." loading="lazy">
<p class="cap">Figure 3 from F. Capozzi, W. Giarè, E. Lisi, A. Marrone,
A. Melchiorri and A. Palazzo, <em>Neutrino masses and mixing: Entering the era
of subpercent precision</em>, Phys. Rev. D <strong>111</strong>, 093006 (2025),
<a href="https://doi.org/10.1103/PhysRevD.111.093006">doi:10.1103/PhysRevD.111.093006</a>.
Published by the American Physical Society under the terms of the
<a href="https://creativecommons.org/licenses/by/4.0/">Creative Commons
Attribution 4.0 International</a> license; reproduced here under those terms.</p>
</figure>

<figure class="figure figure--wide reveal" style="margin-top:1.6rem">
<div class="figure__head">
  <h3>Where θ₂₃ and θ₁₃ meet</h3>
  <p>Fig. 4 of the paper · increasingly rich datasets</p>
</div>
<img src="images/prd111-093006-fig4-th23-th13.png" alt="Regions allowed in the
sin²θ₂₃–sin²θ₁₃ plane for increasingly rich datasets, in normal ordering (top)
and inverted ordering (bottom)." loading="lazy">
<p class="cap">Figure 4 from the same paper, same citation and licence as
above.</p>
</figure>

<figure class="figure figure--wide reveal" style="margin-top:1.6rem">
<div class="figure__head">
  <h3>The same table, seen at a glance</h3>
  <p>best fit · 1σ · 3σ · one shared scale, in % of each best fit</p>
</div>
<!--include:ranges-->
<p class="cap">Every row is centred on its own best fit and measured
outward in percent of it, on one shared axis, so the width of a row is how well
that parameter is known: |Δm²| is measured to ±2.5% at 3σ, while δ in normal
ordering runs off the axis at −39%/+69% and is marked where it leaves. Absolute
values are printed at the right. Values are those of Table I above; the figure
is generated from them by <code>tools/make_figures.py</code>, not drawn by
hand.</p>
</figure>

<div class="split" style="margin-top:2rem">
<div>
<h3>What changed</h3>
<p class="small">|Δm²| is now constrained at the 0.8% level — the first
oscillation parameter to enter the subpercent precision era — against 1.1% in
the previous update; the paper underlines in the same breath that there are
issues about systematics which might affect that error estimate. The
uncertainty on sin²θ₁₃ falls to 2.4%, from about 3%.
For sin²θ₂₃ the two quasi-degenerate minima are closer than before, differing
by roughly 15% against about 25% previously. Constraints on δ are similar to
before within large uncertainties, with a weaker rejection of CP conservation
in NO. The overall offset between the orderings is now Nσ = √5.0 = 2.2, down
from 2.5σ.</p>
</div>
<div class="callout">
<h4>Not included</h4>
<p>The first published SNO+ reactor results are not included: they constrain
δm² with an error larger than the one above by a factor of about 6, and only
under a prior on θ₁₂. SNO+ is nevertheless expected to surpass the present
δm² accuracy on (δm², θ₁₂) within a few years.</p>
</div>
</div>

<div class="callout" style="margin-top:2rem">
<h4>Since this release: the (1,&nbsp;2) sector, updated</h4>
<p>A partial update revises two of the six parameters above.
<a href="https://doi.org/10.1103/cxqw-1bty">Phys. Rev. D 114, 016026
(2026)</a> (<a href="https://arxiv.org/abs/2511.21650">arXiv:2511.21650</a>)
adds the first JUNO results and the latest SNO+ data to the 2025 analysis and
gives δm² = 7.48 (1σ 7.39 – 7.58) in units of 10⁻⁵ eV² and
sin²θ₁₂ = 0.3085 (1σ 0.3010 – 0.3156). It quotes no new values for |Δm²|,
sin²θ₁₃, sin²θ₂₃ or δ, which stand as in the table above. Both releases are on
the <a href="history.html">parameter history</a>, with the table each number
was transcribed from.</p>
</div>

</div>

:::

::: section #data

<div class="section-head">
  <h2>Machine-readable data</h2>
  <p>planned for this release</p>
</div>

<div class="prose">
<p>Δχ² profiles and the tables above will be published here as documented files
at stable URLs — the kind of thing you can fetch from a script and cite — under
<code>data/&lt;release&gt;/</code>. They are exported from the analysis by a
dedicated step; the analysis code itself stays where it belongs and is never
part of this site.</p>
<p>Nothing is linked from this section yet: the export runs when the release
material is prepared, and a link that does not resolve is worse than no link.
What does exist today is the parameter register — every value on this site,
with its source — published as JSON and CSV on the
<a href="history.html#data">parameter history page</a>.</p>
</div>

:::

::: section alt

<div class="strip reveal">
  <a href="history.html"><span class="t">Parameter history</span><span class="d">How these numbers moved over a quarter century, and how other groups’ compare</span></a>
  <a href="about.html#cite"><span class="t">How to cite</span><span class="d">BibTeX for the current release</span></a>
  <a href="resources.html"><span class="t">Resources</span><span class="d">The experiments and data releases that feed a global analysis</span></a>
</div>

:::
