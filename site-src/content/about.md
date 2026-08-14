---
title: About
url: about.html
description: >-
  Who publishes global-nu.org, what a global analysis is, and how to cite the
  releases.
katex: false
---

<section class="hero">
  <div class="wrap hero__in">
    <p class="kicker">About</p>
    <h1>About this site</h1>
    <p class="lede">A site of the Bari group, built to put our global analyses
    of neutrino oscillation data — and the material around them — where the
    community can actually use them.</p>
  </div>
</section>

::: section

::: split

::: prose

## The group

The global analyses published here are the work of a collaboration centred on
Bari. The most recent release,
<a href="https://doi.org/10.1103/PhysRevD.111.093006">Phys. Rev. D 111, 093006
(2025)</a>, is by <strong>Francesco Capozzi</strong> (L’Aquila and INFN LNGS),
<strong>William Giarè</strong> (Sheffield), <strong>Eligio Lisi</strong> (INFN
Bari), <strong>Antonio Marrone</strong> (Università di Bari and INFN Bari),
<strong>Alessandro Melchiorri</strong> (Roma “La Sapienza” and INFN Roma I) and
<strong>Antonio Palazzo</strong> (Università di Bari and INFN Bari).

The series of analyses it belongs to goes back to the early 2000s; the
[parameter history](history.html) page traces it release by release.

## What a global analysis is

Every oscillation experiment measures a projection of the same six-parameter
space, and each is blind to directions the others constrain. A global analysis
combines them into a single χ² — solar, atmospheric, reactor and accelerator
data, with cosmological constraints where relevant — and reports the parameters
with the correlations intact. That combination is what this site publishes.

:::

<div>

<div class="callout" id="cite">
<h4>How to cite</h4>
<p>If you use the numbers or the files from the 2025 release, please cite the
paper:</p>
<pre style="overflow-x:auto;font-family:var(--mono);font-size:.78rem;line-height:1.5;margin:.6rem 0 0"><code>@article{Capozzi:2025wyn,
  author  = {Capozzi, Francesco and Giar\`e, William
             and Lisi, Eligio and Marrone, Antonio
             and Melchiorri, Alessandro and Palazzo, Antonio},
  title   = {{Neutrino masses and mixing:
             Entering the era of subpercent precision}},
  journal = {Phys. Rev. D},
  volume  = {111},
  number  = {9},
  pages   = {093006},
  year    = {2025},
  doi     = {10.1103/PhysRevD.111.093006},
  eprint  = {2503.07752},
  archivePrefix = {arXiv},
  primaryClass  = {hep-ph}
}</code></pre>
<p class="small" style="margin-top:.7rem">The INSPIRE record carries the
authoritative key and an always-current BibTeX entry:
<a href="https://inspirehep.net/literature?q=arxiv:2503.07752">look it up on
INSPIRE</a>.</p>
</div>

<div class="callout" style="margin-top:1.3rem">
<h4>Automatically generated pages</h4>
<p>Three pages are rebuilt every morning by a job on our own machine, and each
one carries a notice saying so. The <a href="digest.html">arXiv digest</a> and
the <a href="conferences.html">conference calendar</a> are produced by a script
from the arXiv and Indico APIs, with no model involved at any point. The
<a href="news.html">news</a> page is different: its summaries are written by a
language model from fetched records, and every citation in them is checked
against those records before the page is written. All three may contain
errors, and none is a substitute for the sources it links to.</p>
<p>The <a href="results.html">results</a> and the
<a href="history.html">parameter history</a> are not automated: every number
there is transcribed from a published table by hand.</p>
</div>

</div>

:::

:::

::: section alt glow

::: split
::: prose

## Contact

Dipartimento Interateneo di Fisica “Michelangelo Merlin”, Via Amendola 173,
<!-- Postcode 70126, confirmed by Antonio on 2026-08-14. A pre-launch audit
     could not source it: UniBa serves crawlers a stub, INFN Bari publishes a
     different street (Via Orabona 4, 70125), and OpenStreetMap returns 70121
     and 74126 for Via Amendola. It is what the group's own papers print, and
     it is the address of the person who works there. Do not "correct" it from
     a web search. -->
70126 Bari, Italy — Università degli Studi di Bari “Aldo Moro” and INFN Sezione
di Bari.

Write to <a href="mailto:antonio.marrone@ba.infn.it">antonio.marrone@ba.infn.it</a>.

:::
::: prose

## How this site is built

Static pages, no server-side code, no cookies. Every font, stylesheet and
script — including the counter's — is served from this domain: no page loads
anything from a third-party host. The literature [search](search.html) runs
entirely in your browser: what you type goes directly from you to the
databases, and never to this site.

Visits are counted with GoatCounter, which records a pageview without cookies
and without tracking individuals. That is the one request a page makes off this
domain: one counting request per pageview, to
<code>global-nu.goatcounter.com</code>.

## Licensing {: #licence }

Not one licence for everything. The parameter register and the data files it
is exported to are published under
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>: use them,
crediting this site and citing the paper each number came from. The text of
these pages and the code that builds them are all rights reserved. Figures
reproduced from published papers, and the photographs on the map, travel under
their own terms, credited beside each one — a figure from
<a href="https://doi.org/10.1103/PhysRevD.111.093006">Phys. Rev. D 111,
093006</a> is here under the CC BY 4.0 licence of the paper, and a CC BY-SA
photograph stays CC BY-SA.

:::
:::

:::
