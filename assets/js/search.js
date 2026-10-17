/* =====================================================================
   search.js — free-form literature search across INSPIRE-HEP, Crossref
   and OpenAlex, plus outbound links to arXiv, ADS and Google Scholar.

   Pure client-side: the visitor's browser talks to the APIs directly.
   Nothing is sent to global-nu.org, no key is embedded, no tracking.

   Only INSPIRE, Crossref and OpenAlex send CORS headers, so only those
   three can be rendered in-page. arXiv, ADS and Scholar are offered as
   prepared queries that open in a new tab.
   ===================================================================== */
(function () {
  "use strict";

  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var form = $("#lit-form");
  if (!form) return;

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  var elFree     = $("#q-free");
  var elAuthor   = $("#q-author");
  var elTitle    = $("#q-title");
  var elTopic    = $("#q-topic");
  var elFrom     = $("#q-from");
  var elTo       = $("#q-to");
  var elCollab   = $("#q-collab");
  var elResults  = $("#lit-results");
  var elSortBar  = $("#lit-sort");
  var elFilters  = $("#lit-filters");
  var elStatus   = $("#lit-status");
  var elOutbound = $("#lit-outbound");
  var elChips    = $("#lit-chips");
  var elBadges   = $("#lit-badges");
  var elMode     = $("#lit-mode");
  var elTime     = $("#adv-time");
  var elDisc     = $("#adv-disc");
  var elAdv      = $("#lit-adv");

  // The badge row is drawn by this script; the page provides it, but a
  // page without it (the sort test builds a minimal one) still works.
  if (!elBadges && elResults) {
    elBadges = document.createElement("div");
    elBadges.id = "lit-badges";
    elResults.parentNode.insertBefore(elBadges, elResults);
  }

  /* ---------------------------------------------------------------
     1. Parsing the free-form line
     --------------------------------------------------------------- */

  var MONTHS = {
    jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
    jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12
  };

  // Words that are never author surnames even when capitalised. Two fates:
  // DROP is search grammar that carries no meaning for any database; KIND is
  // the document type the reader is after ("lecture notes", "review") — it
  // used to be dropped with the grammar, which silently turned "lecture
  // notes string theory" into a bare "string theory" search. KIND words are
  // real query terms: they go to the topic, just never to an author guess.
  var DROP = new Set((
    "a an an the of in on for with without from to by as at or not new " +
    "paper papers preprint about search find " +
    "all any between since after before during last recent latest recently " +
    "year years month months day days week weeks and et al"
  ).split(" "));
  var KIND = new Set((
    "review reviews lecture lectures notes note thesis theses " +
    "introduction introductory course courses primer textbook textbooks " +
    "pedagogical school schools"
  ).split(" "));

  // Subject vocabulary. A leftover word that appears here is a topic. Anything
  // else is a topic too, UNLESS the query says it is a person (see the author
  // rules in parseFree): the old reading — every leftover alphabetic word is a
  // surname, whatever its case — turned "determination", "long-baseline" and
  // "medium-baseline" into authors. Wrong guesses are visible in the chips and
  // can be corrected in the fields below.
  var PHYS = new Set((
    "neutrino neutrinos antineutrino oscillation oscillations mixing mass " +
    "masses massless splitting hierarchy ordering flavour flavor lepton " +
    "leptonic leptons quark quarks fermion fermions boson bosons " +
    "seesaw majorana dirac sterile weyl chirality helicity spinor " +
    "cp violation phase phases matrix pmns ckm unitarity " +
    "decay decays beta double neutrinoless bb 0nbb halflife " +
    "solar atmospheric reactor accelerator baseline geoneutrino supernova " +
    "cosmology cosmological cosmic relic cmb structure lensing dark matter " +
    "energy baryon asymmetry leptogenesis nucleosynthesis bbn " +
    "symmetry symmetries modular forms group groups discrete abelian " +
    "invariance invariant orbifold compactification string strings " +
    "gut unification unified proton su so pati salam " +
    "standard model beyond bsm effective field theory eft smeft operator " +
    "interaction interactions nsi coupling couplings yukawa higgs " +
    "renormalization renormalisation loop loops radiative anomaly " +
    "cross section scattering coherent cevns elastic inelastic " +
    "global analysis analyses fit fits bounds constraints limits limit " +
    "precision statistical bayesian likelihood chi2 sensitivity " +
    "detector detectors experiment experiments measurement measurements " +
    "spectrum spectra flux fluxes background signal systematics " +
    "matter msw resonance vacuum propagation coherence decoherence " +
    "physics particle nuclear astroparticle astrophysics phenomenology " +
    "theory theoretical model models mechanism mechanisms scale scales " +
    "quantum relativistic classical electroweak strong weak gauge " +
    "axion axions monopole magnetic moment dipole portal " +
    "prediction predictions correlation correlations degeneracy"
  ).split(" "));

  // Words of real abstracts (lower case, and eponyms such as "Hubble").
  /* VOCAB:BEGIN — generated by tools/search_vocab.py from arXiv abstracts; do not edit */
  var VOCAB_LOWER = new Set("abacussummit abcmb abelian abilities ability able aboard about above abridged abrupt abruptly absence absent absolute absolutely absorb absorbed absorber absorbers absorbing absorbs absorption abundance abundances abundant abundantly abyss accelerate accelerated accelerates accelerating acceleration accelerations accelerator accelerators acceptable acceptance acceptances accepted accepts access accessed accessibility accessible accessing accidental accidentally accommodate accommodated accommodates accommodating accompanied accompany accompanying accomplished accordance according accordingly account accounted accounting accounts accrete accreted accretes accreting accretion accumulate accumulated accumulates accumulating accumulation accuracies accuracy accurate accurately achievable achieve achieved achievement achievements achieves achieving acis acot acoustic acquire acquired acquires acquiring acquisition across act acting action actionable activated activation active actively activities activity acts actual actually adapt adaptation adaptations adapted adapting adaptive adc add added adding addition additional additionally additions additive address addressed addresses addressing adds adequate adequately adf adhere adhering adiabatic adiabatically adiabaticity adjacent adjoint adjust adjustable adjusting adjustment adjustments adm admits admixture adonis adopt adopted adopting adoption adopts ads adsorbent adsorption advance advanced advancement advancements advances advancing advantage advantageous advantages advected advection advective advent adversarial advocate affect affected affecting affects afforded aforementioned after afterglow afterglows aftermath afterpulse afterpulses afterpulsing again against age agent agents ages aggregate agn agnostic agns ago agree agreement agreements agrees ahead ai aic aid aided aiding aim aimed aiming aims air airplanes akin alarm albeit alert alerts algebra algebraic algebraically algorithm algorithmic algorithms alice align aligned alignment alignments aligns aligo alike alive all alleviate alleviated alleviates alleviating alleviation allocation allow allowed allowing allows alloy alloys alma almn almost alone along alongside alp alpha alps already also alter altered altering alternate alternately alternating alternative alternatively alternatives alters although altitude altitudes always am amazing amber ambient ambiguities ambiguity ambiguous ambipolar ambitious ames amon among amongst amount amounts amplification amplified amplifier amplifies amplify amplifying amplitude amplitudes amrex analog analogous analogously analogue analogues analogy analyse analysed analyses analysing analysis analytic analytical analytically analyze analyzed analyzes analyzing anapole anarchic anarchical anarchy anchor anchored ancient ancillary and angle angles angular anisotropic anisotropies anisotropy anita ankle annealing annie annihilate annihilates annihilating annihilation annihilations announced annual annulus anode anomalies anomalons anomalous anomalously anomaly another ansatz answer answers antares antenna antennas antesonic anthropogenic antialigned anticipate anticipated antikaon antilepton antimatter antimuons antineutrino antineutrinos antiparticle antiparticles antiproton antisymmetric anubis any anyon anything anywhere ao apart aperture apex api apparatus apparent apparently appealing appear appearance appeared appearing appears applicability applicable application applications applied applies apply applying appreciable appreciably approach approached approaches approaching appropriate appropriately approved approx approximate approximated approximately approximating approximation approximations apps apr apv aqe ara arasim arbitrarily arbitrariness arbitrary arc arca arcade archaeological architecture architectures archival are area areas argon arguably argue argued argument arguments arise arises arising arithmetic arm around arrange arranged arrangement arrangements array arrays arrested arrival arrive arrives arriving ars art article artifact artifacts artificial artificially as ascension ascertain ascribed asic asics ask askap aspect aspects aspherical assay assays assembled assembly assess assessed assesses assessing assessment assessments assign assigned assigning assignment assignments assigns assimilation assist assistance assisted associate associated association associations assume assumed assumes assuming assumption assumptions assure assures asteroid asteroseismology astra astrometry astronomical astronomy astroparticle astrophysical astrophysically astrophysics asymmetric asymmetrically asymmetries asymmetry asymptotic asymptotically at atlas atmosphere atmospheres atmospheric atns atom atomic atomki atoms attached attack attain attainable attained attains attempt attempted attempting attempts attention attenuate attenuated attenuation attracted attractive attributable attribute attributed attributes aturalness auc auger augerprime augmentation augmented austral author authors autoencoder autoencoders automate automated automatic automatically automating autonomous autonomously autoregressive autotherm auxiliary availability available avalanche avalanches avenue avenues average averaged averages averaging avoid avoided avoiding avoids away axes axial axially axioelectric axion axionlike axions axis axisymmetric azimuth azimuthal ba babar bacco back backbone background backgrounds backreaction backward backwards bag balance balanced balances balancing balloon balloons band bandpowers bands bandwidth bang bangs bao baos bar bare barely barium barrier barriers bars baryogenesis baryon baryonic baryonification baryons base based baseline baselines bases basic basis bat batch bath baths bau bayeswave bbdm bbh bbhs bbn bbo bbzz bcs bdf bdm bdt bdx be beacon beam beamed beamformer beaming beamline beamlines beams bearing bears became because become becomes becoming bed been before began begin beginning begins behave behaves behavior behaviors behaviour behaviours behind being believe believed belong belonging belongs below bench benchmark benchmarked benchmarking benchmarks bend bending beneath beneficial benefit benefiting benefits bent beryllium beside besides besiii best beta better between beyond bgk bgo bh bhde bhdpe bhs bhxbs bias biased biases biasing bidoublet bifurcation big bigger biggest bilinear bilinears billions bimodal bin binaries binary binding binned binning bino binomial bins biofouling bipartite bipolar birefringence birth bispectra bispectrum bit bits bl black blackbody blast blastwave blastwaves blazar blazars blind blinded blindness blip blips blob blobs block blocking blocks blowout blr blsm blue bm bnb bnl bns bnsm bnsms bnt bnv board boards bodies body bolometers bolometric bomb bonus boomerang boost boosted boosting boosts bootstrap borehole boreholes borexino born boson bosonic bosons boss both bottleneck bottlenecked bottom bounce bound boundaries boundary bounded bounding bounds box boxes bps branch branches branching brand brane breadth break breakdown breaking breakout breakouts breaks breakthrough breakup bremsstrahlung bridge bridging brief briefly bright brighten brightening brightens brighter brightest brightness bring bringing brings broad broadband broaden broadened broadening broadens broader broadly broken brought bs bsgs bsm bthde bubble bubbles budget budgets buffer build building builds built bulk bullkid bump bunch bundle bundles burden burdened buried burning burst bursts but bypass bypasses byproduct bz cable cabled cadence cage calculable calculate calculated calculates calculating calculation calculations calculator calet calibrate calibrated calibrating calibration calibrations call called calls calorimeter calorimeters calorimetric calorimetry came camera campaign campaigns camspec can cancel canceled cancellation cancellations cancelled cancels candela candidate candidates candle candles cannot canonical caons capabilities capability capable capacity capped captions capture captured captures capturing carbon care career careful carefully carried carrier carries carry carrying cascade cascades case cases cast catalog catalogs catalogue catalogues catalysis catalyzed catastrophic catch catcher categories categorized category cathode causal cause caused causes causing caution caveats cavern cavities cavity cawo cbs cc cca ccbh ccm cco ccos ccqe ccsn ccsne ccsnr cdf cdm cdrl ce ceiling celestial cell cells censored census center centered centers centimeter central centre centrifugal century cepc cer cern certain certificates cesium cessation cevns cfc cfi cfl cft cgb cgcg cgm cgrabs ch chain chained chains challenge challenged challenges challenging chamber chambers chance chances change changes changing channel channeling channels chaotic chapter character characterisation characterise characterised characteristic characteristics characterization characterizations characterize characterized characterizes characterizing charcoal charge charged chargephobic charges charginos charm charmed chart chde cheaper check checked checking checks chemical chemistry chi chic chiral chirality chirally chlorine choice choices choked choking choose choosing chosen chpt chromodynamics cib circuit circuits circular circulation circumbinary circumgalactic circumnuclear circumstellar circumvent circumvented circumventing circumvents cis civil cjpl ckm cl claim claimed claims clarifies clarify clarifying clas class classes classic classical classicality classically classier classification classifications classified classifier classifiers classifies classify classifying clean cleaning cleanliness clear clearest clearly clfv clic clock clocking clocks cloe close closed closely closeness closer closes closest closing closure closures cloud clouds cls clues clump clumps clumpy cluster clustering clusters cm cmb cmbcomp cmbolic cmf cmos cms cmz cn cnb cnm cnn cnns cno cnuf co coalescence coalescences coannihilation coarse coated coating cob cobimaximal cocoon cocoons code coded codes coding coefficient coefficients coexist coexistence coexisting cogenesis coherence coherences coherent coherently coincide coincidence coincidences coincident coincides coinciding cold coldadc coldbox colder collaboration collaborations collaborators collapsar collapsars collapse collapsed collapses collapsing collect collected collecting collection collective collectively collide collider colliders colliding collimated collinear collision collisional collisionally collisionless collisions color colored colors colour column columns combination combinations combinatorial combine combined combines combining come comes comet comfortably coming commence commensal comment commented comments commercial commissioned commissioning common commonly communicate communicates communication communities community commuting comoving compact compactification compactifications compactified compactness companion comparable comparably comparative comparatively compare compared compares comparing comparison comparisons compatibility compatible compelling compensate compensated compensates compensating compensation compete competing competition competitions competitive competitiveness compilation compilations compile compiled compiles compiling complement complementarities complementarity complementary complemented complementing complements complete completed completely completeness completes completion completions complex complexified complexities complexity complicated complicating complication comply complying component components composable compose composed composing composite compositeness composites composition compositional compositions compounds comprehensive comprehensively compressed compresses compressing compression compressions comprise comprised comprises comprising compromise compromising comptel computation computational computationally computations compute computed computer computers computes computing concave conceived concentrate concentrated concentrating concentration concentrations concentrator concentrators concentric concept concepts conceptual conceptually concern concerned concerning concerns concise conclude concluded concludes concluding conclusion conclusions conclusive conclusively concordance concordant concrete concreteness concurrence concurrent concurrently condensate condensates condensation condensed condition conditional conditioned conditions conducive conduct conducted conducting conductivity cone conference confidence configuration configurations confine confined confinement confines confining confirm confirmation confirmed confirming confirms conflict conflicting conflicts conflux conformal conformally confront confronted confronting confronts confusion congruence conjectured conjugate conjugation conjunction connect connected connecting connection connections connectivity connects consecutive consensus consequence consequences consequent consequentially consequently conservation conservative conservatively conserve conserved conserving consider considerable considerably consideration considerations considered considering considers consist consistency consistent consistently consisting consists consolidating consortium constancy constant constantly constants constellation constituent constitute constitutes constituting constrain constrained constraining constrains constraint constraints construct constructed constructing construction constructions consumed consumer consuming consumption contact contain contained containers containing containment contains contaminant contaminants contaminate contamination contemporaneous contemporary contenders content context contexts contextualize contextualizes contextualizing continua continually continuation continue continued continues continuing continuity continuous continuously continuum contour contours contraction contractions contradict contrary contrast contrasted contrasting contrastive contrasts contribute contributed contributes contributing contribution contributions contributor contributors control controlled controlling controls controversial conus convection convective convenient conveniently conventional conventionally converge converged convergence converges conversion conversions convert converted converters converting converts convex convincing convolution convolutional convolutions convolve cool cooled cooler cooling cools coordinate coordinated coordinates coordination copies copious copiously copper coprocessors core cores corner cornerstone corollary corona coronae coronal corotation correct corrected correcting correction corrections correctly corrects correlate correlated correlates correlating correlation correlations correlator correlators correspond correspondence corresponding correspondingly corresponds corsika coscattering cosi cosine cosinus cosmic cosmogenic cosmological cosmologically cosmologies cosmology cosmos cost costly costs could count counter counterpart counterparts counterterm counterterms counting counts couple coupled couples coupling couplings course covariance covariances covariant covariants cover coverage covered covering covers cp cpc cpl cpt cpu cpus cpv cpvs cr cracks crb crc crdm create created creates creating creation credibility credible cres crex crisis crisp criteria criterion critical criticality critically cross crossed crosses crossing crossings crossover crossroads crosstalk crpropa crs crt crucial crucially crust crustal crusts cryogenic cryostat cryostats crystal crystalline crystallization crystals csc csi csm csst ct cta ctao cube cubes cubesat cubic cuboid culminating cumulative cuore cupid current currently currents curvature curve curved curves cuspy custodial custom customized cut cutoff cutoffs cuts cw cwb cycle cycles cyclic cyclotron cyclotrons cygno cylindrical cz daily damage dampe damped damping damsa dangerous danss daq dar dark darwin data database databases dataset datasets date daughter daughters dawn day days db dbd dbdm dbds dcc dce dcr dd dde ddm de dead deadtime dealing death deaths debate debated debris dec decade decades decay decaying decays deceleration decided decigo decipher deciphering decision decisive decisively declare declination declinations decline decoherence decompose decomposed decomposing decomposition deconfined deconfinement deconstruction deconvolution decouple decoupled decouples decoupling decrease decreased decreases decreasing dedicated deduced deep deepcore deepen deepens deeper deepest deeply deepmet deexcitation defect defective defects deficiencies deficiency deficit define defined defines defining definite definition definitions definitive deflected deflection deflections deflects deformability deformation deformations deformed deg degassing degeneracies degeneracy degenerate degradation degrade degraded degrades degrading degree degrees del delay delayed delaying delays deleptonization delineate delineating deliver delivered delivering delivers delivery dell delta demand demanding demands democratic demographics demonstrate demonstrated demonstrates demonstrating demonstration demonstrator denoiser denoising denominator denote denoted denotes denoting dense densely denser densest densities density depart departure departures depend dependence dependencies dependency dependent depending depends dephasing deplete depletion deploy deployed deploying deployment deposit deposited deposition depositions deposits depth depths derivation derivations derivative derivatives derive derived derives deriving des describe described describes describing description descriptions descriptors desert desi design designated designed designing designs desirable desired despite destroy destroyed destruction destructive detail detailed detailing details detect detectability detectable detected detecting detection detections detector detectors detects deteriorate deteriorated deteriorates determinant determination determinations determine determined determines determining deterministic detonation deuterium deuteron deuterons develop developed developer developing development developmental developments develops deviate deviates deviating deviation deviations device devices devise devoted dex dfsz dft dhva diagnose diagnostic diagnostics diagonal diagonalization diagonalize diagonalized diagram diagrams diameter dictate dictated dictates dictating did dielectric dielectron differ difference differences different differentiable differential differentiate differentiated differentiating differentiation differently differing differs difficult difficulties difficulty diffractive diffuse diffused diffusion diffusive diffusivity digital digitised digitization digitizers dijet dilation dilemma dilepton dileptonic dileptons dilute diluted dilutes diluting dilution dim dimension dimensional dimensionality dimensionally dimensionless dimensions diminishes diminishing dimuon dimuons dineutrino dio diode dip diphoton diphotons dipolar dipole dipoles dips diquark direct directed direction directional directionality directions directly dirt dirty dis disagreement disagreements disallowed disappear disappearance disappearing disc discernible disciplines disconnected discontinuities discover discovered discoveries discovering discovery discrepancies discrepancy discrepant discrete discreteness discretization discretize discretized discriminants discriminate discriminated discriminating discrimination discuss discussed discusses discussing discussion discussions disentangle disentangling disfavor disfavored disfavoring disfavors disfavour disfavoured disfavours disintegration disk disks disorder disordered disparate disparity dispersion dispersions dispersive displaced displacement display displaying displays disrupted disruption disrupts dissecting dissipated dissipation dissipative dissolved distance distances distant distillation distinct distinction distinctive distinctly distinguish distinguishability distinguishable distinguished distinguishes distinguishing distorted distortion distortions distributed distribution distributional distributions disturbance diverge divergence divergences divergent diverges diverse diversity divide divider dla dlrsm dm dmdsnb dmp dms dnn dnnb document documentation documented does doing domain domains dominance dominant dominantly dominate dominated dominates dominating domination doms done doomsday door doped doping dots double doublet doublets doubly down downgoing downstream downward dozen dozens dp dpf dps dr drag dramatic dramatically drastic drastically drawing drawn dream dressed drift drifts drilling drive driven driver drivers drives driving drop drops ds dsa dsfg dsfgs dsmc dsnb dsph dsphs dss dts du dual duality dub dubbed due dumand dump dumps dune duplication duration durations durca during dust dusty duty dv dw dwarf dwarfs dws dynamic dynamical dynamically dynamics dynamo dynode each ear earlier earliest early earth eas ease eases easier easily easing eass east easy eboss ec ecec echo echoes economical ecore ecrs ecs ede edge edges edition edm edms ee eev effect effective effectively effectiveness effects efficacy efficiencies efficiency efficient efficiently effort efforts eft eftoflss efts eger egmf ehe ehp eic eigenbasis eigenfrequencies eigenstate eigenstates eigenvalue eigenvalues eight either eject ejecta ejected ejection ejects elaborate elastic elastically electric electrical electrically electrode electrodes electroformed electroluminescence electromagnetic electromagnetically electromagnetism electron electronic electronics electrons electrophilic electrosphere electrostatic electroweak electroweakino electroweakly elegant elegantly element elemental elementary elements elevate elevated elevation eleven elica eliminate eliminated eliminates eliminating ellipticals eln elongated elucidate elucidates elucidating elusive em emanating emanation embed embedded embedding emd emerge emerged emergence emergent emerges emerging emf emission emissions emissivities emissivity emit emits emitted emitter emitters emitting emphasis emphasise emphasize emphasized emphasizes emphasizing empirical empirically employ employed employing employs empress empty emt emulate emulating emulation emulator emulators emulsion enable enabled enables enabling enantiomeric enclosed encode encoded encoder encodes encoding encodings encompass encompasses encompassing encounter encountered encounters encourage encouraged end endeavor ended endorsed endothermic endowed endpoint ends energetic energetically energetics energies energize energized energy enforce enforced enforces enforcing engaged engine engineering engines engulfed enhance enhanced enhancement enhancements enhances enhancing enigmatic enlarged enlarges enlarging enormous enough enrich enriched enrichment ensemble ensembles ensuing ensure ensured ensures ensuring entail entangled entanglement entangling enter entered entering enters entertain entire entirely entirety entrance entries entropy entry enubet enumerate envelope envelopes environment environmental environments envisaged envisioned eof eor eos eoss ep episode episodes episodic epistemic epistemically epoch epochs epsilon equal equality equally equals equation equations equator equatorial equilateral equilibrate equilibrated equilibration equilibria equilibrium equipartition equipment equipped equivalence equivalent er era erased erasing erg ergosphere erosita error errors eruption eruptions eruptive erythrohenosis es escape escaped escaping especially esr ess essential essentially essnusb essnusbplus establish established establishes establishing estes estimate estimated estimates estimating estimation estimations estimator estimators et eta etc ethos ev eva evade evaded evades evading evaluate evaluated evaluates evaluating evaluation evaluations evaporate evaporated evaporating evaporation evaporative evee even event events eventual eventually ever every everyday evidence evidences evidential evolution evolutionary evolutions evolve evolved evolves evolving evpa ew ewpt exacerbated exact exactly examination examine examined examines examining example examples exceed exceeded exceeding exceeds excellent excellently except exceptional exceptionally excess excesses excessive excessively exchange exchanges exchanging excision excitation excitations excite excited excites exciting exclude excluded excludes excluding exclusion exclusive exclusively excursions execution exemplified exemplify exercises exhaustive exhibit exhibited exhibiting exhibits exist existence existing exists exit exoplanet exoplanets exothermic exotic exp expand expanded expanding expands expansion expansions expect expectation expectations expected expects expedite expelled expense expensive experience experienced experiences experiment experimental experimentalists experimentally experiments expert experts explain explainability explained explaining explains explanation explanations explanatory explicit explicitly explodability explode exploding exploit exploitation exploited exploiting exploits exploration explorations exploratory explore explored explores exploring explosion explosions explosive exponent exponential exponentially exponents expose exposed exposes exposing exposure exposures express expressed expression expressions expulsion extend extendable extended extending extends extensibility extension extensions extensive extensively extensivity extent external externally extinction extp extra extract extracted extracting extraction extractions extracts extragalactic extraordinarily extraordinary extrapolate extrapolated extrapolation extraterrestrial extreme extremely extrinsic extruded fabricated fabrication face faced faces facet facie facilitate facilitated facilitates facilitating facilities facility facing fact factor factories factorization factorized factors factory facts fade fading faerie fail failed failing fails failure failures faint fainter fair faithful fake fall fallback falls false falsifiable falsified familiar families family fapr far farther farview fascinating faser fasernu fashion fast faster fastest fat fate fates fatjet favor favorable favored favoring favors favour favourable favoured favours fbk fbots fcc fcnc fcncs fd fdm fds feasibility feasible feature featured features featuring feb febs feeble feebly feed feedback feeding femtoscopy fermion fermionic fermions few fewer feynrules ff ffc ffcs ffi ffr fft fi fiber fiberglass fibers fibres fidelity fiducial field fields fifth figure filamentary filaments file files fill filled filling film films filter filtering filters fimp fimps final finally find finding findings finds fine finely fingerprints fingers finite fips fireball fireshell firm firmly firmware firn first fission fit fits fitted fitting five fix fixed fixes fixing fkm flagship flamingo flare flares flaring flash flashes flat flatness flattening flattens flatter flavomon flavomons flavon flavons flavor flavored flavorful flavors flavour flavoured flavours flexibility flexible flight flip flipped floor floors flow flowing flown flows flt fluctuates fluctuating fluctuation fluctuations fluence fluences fluid fluids fluorescence fluoride fluorine flux fluxes flying fm fn fnal foam foc focal focus focused focuses focusing focussing fog folded folding follow followed following follows footage footing footprint fopt for forbid forbidden forbidding forbids force forced forces forcing forecast forecasted forecasting forecasts forefront foreground foregrounds foreseeable foreseen foresees forest form formal formalism formalisms formalize format formation formed former formidable forming formosa forms formula formulae formulas formulate formulated formulating formulation formulations forth forthcoming forty forward foster found foundation foundational foundations four fourteen fourth fov fp fpf fpga fpgas fps fr fraction fractional fractionally fractions fragile fragment fragmentation fragments frame framed frames framework frameworks frb frbs free freedom freeing freely freeze freezeout frequencies frequency frequent frequentist frequently fresh frib friction frictional frii from front frontend frontier frontiers fronts frozen fs fsi fsnd fsrq fsrqs fts fuel fulfil fulfill fulfilled fulfilling full fully function functional functionalities functionally functionals functioning functions fundamental fundamentally funded funnel further furthermore fusion future futuristic fuzzy fwhm fx gadolinium gagg gain gained gaining gains galactic galaxies galaxy gallery gallex gallium galprop game gamma gammatpc gan ganess gap gape gapless gapped gaps gas gaseous gases gate gated gates gateway gathered gauge gauged gauging gaugino gauginos gb gc gce gcp gcrs gen general generalise generalised generality generalization generalizations generalize generalized generalizes generalizing generally generate generated generates generating generation generational generations generative generator generators generic generically genie genuine genuinely geochemical geodesic geographic geological geomagnetic geometric geometrical geometrically geometries geometry geoneutrino geoneutrinos geophysical geoscience gerda germanium get gets getting gev gf gfu gh ghost ghz giant giants gibuu gigantic gim ginkaku github give given gives giving glacial glass glip global globally globes globular gluon gluons gm gmsugra gni gnm gnmssm gnn gnns goal goals goes going gokunemu gold golden gollumfit gone goniometer good goodness govern governed governing governs gp gps gpu gpus gr grade gradient gradients gradual gradually graduate grafei grains grammage grammar grams grand granular granularity graph graphene graphical graphnet gravitating gravitation gravitational gravitationally gravitino gravitinos graviton gravitons gravity gray grb grbs great greater greatest greatly grendel grhayl grid grids grinta grm grmhd ground groundbreaking grounded grounds groundwork group grouped groups grow growing grown grows growth grrmhd gs gsi gso gstlal gt gtr guarantee guaranteed guarantees guidance guide guided guides guiding gun gut guts gvd gw gws gxe gygag gyroscope had hadron hadronic hadronically hadronisation hadronization hadronize hadrons hadronuclear half hall halo haloes halos hampered hand handed handful handle handled handles handling happen happens harbor harboring hard hardening harder hardly hardware harmonic harmonics harsh has have having hawc hayesep hazardous hb hbls hcfi hd hde hdm hdom hdpe he head healpix hearts heat heating heats heavier heaviest heavily heavy hecap hecos heft height heightened held helical helicities helicity helioscope helioscopes helioseismic heliosphere heliospheric helium help helpful helping helps hemera hemisphere hemispheres hemt hence hep her hera herbs here hereafter hermetic heron hese hess heteroclinic heterogeneous heuristic hexadecapole hf hfir hh hi hiaf hidden hide hierarchical hierarchies hierarchy higgs higgsino higgsinos high higher highest highlight highlighted highlighting highlights highly hii hilltop hinder hindered hint hinted hinting hints his historic historical historically histories history hit hitherto hits hk hl hm hmf hmns hnl hnls hoc hod hold holds hole holes holistic holmes holographic holomorphic homochirality homogeneous homologous homology horizon horizons horizontal horizontally horn hos host hosted hosting hosts hot hotspot hotspots hotter hour hours house housed how however hpge hpk hrc hrs hsp hst htl hub huge human humidity hundred hundreds hunt hv hvp hvs hy hybrid hybridization hydrocarbon hydrodynamic hydrodynamical hydrodynamics hydrogen hydrophone hydrophones hydrostatic hyperaccreting hyperbolic hypercharge hypercharges hypercritical hypercube hyperfine hypermassive hypernovae hypernuclear hypernuclei hyperon hyperonic hyperons hypersurface hypotheses hypothesis hypothesize hypothesized hypothetical ia iacts iaea ibd ibds ibh ibhs ibm ic ical icarus ice iceact iceberg icecube iceman icetop icm icmart icnse icrc ics id idcdm ide idea ideal idealised idealized ideally ideas identical identically identifiable identification identifications identified identifies identify identifying identity idm ifoewpt ifu igm igmf ignition ignore ignored ignoring igws ih ihd ii iib iichep iii iin iip iiser ila ilc ild illinoisgrmhd illuminate illustrate illustrated illustrates illustrating illustration illustrative im image images imaginarity imaginary imaging imbalance imbh imbhs ime imes immediate immediately immense immersed imminent immune impact impacted impactful impacting impacts imparting impede imperative imperfect implement implementation implementations implemented implementing implements implication implications implicit implicitly implied implies imply implying importance important importantly impose imposed imposes imposing impossible impractical impressive imprint imprinted imprinting imprints improve improved improvement improvements improves improving impulse impulsive impurities impurity imsst inability inaccessible inaccuracies inaccurate inadequate inc incarnations incidence incident inclination inclined include included includes including inclusion inclusive incoh incoherent incoming incompatibility incompatible incomplete inconclusive inconsistencies inconsistency inconsistent incorporate incorporated incorporates incorporating incorporation incorrect incorrectly increase increased increases increasing increasingly incredibly increment incur incurs indeed independence independent independently index indicate indicated indicates indicating indication indications indicative indicator indices indirect indirectly indispensable indistinguishable indium individual individually induce induced induces inducing induction industrial ineffective inefficiency inefficient inelastic inelastically inelasticity inequalities inequality inequivalent inert inertia inevitable inevitably inexpensive inextricably infalling infer inference inferences inferred inferring infers infill infinite infinitely inflation inflationary inflaton inflow influence influenced influences influencing infn inform information informative informed informing informs infrared infrastructure ingredient ingredients inhabit inherent inherently inherited inherits inhibit inhibiting inhomogeneities inhomogeneity inhomogeneous initial initialize initialized initially initiate initiated initiates initiating initiation initiative initiatives initio inject injected injecting injection inner innermost innovation innovations innovative ino input inputs inquiry insensitive insertion inside insight insights inspect inspiral inspiration inspired instabilities instability installation installations installed installing instance instantaneous instantiated instanton instantons instead institutes institutions instrument instrumental instrumentation instrumented instrumenting instruments insufficient insulation intact integer integral integrals integrate integrated integrates integrating integration integrator intelligence intelligent intend intended intense intensities intensity intensive interact interacting interaction interactions interactive interacts interchange interdisciplinary interest interesting interestingly interests interface interfaced interfaces interfacing interfere interference interferometer interferometers interferometric interferometry intergalactic interior interiors interleaved intermediate intermittency intermittent intermixing internal internally international interplay interpolate interpolation interpret interpretability interpretable interpretation interpretations interpreted interpreting intersection interstellar interval intervals intervening interviewed intimately into intrabinary intracluster intractable intraday intranuclear intricate intricately intriguing intriguingly intrinsic intrinsically introduce introduced introduces introducing introduction introductory intuition intuitive invalid invaluable invariance invariant invariants inventory inverse inversely inversion inverted invested investigate investigated investigates investigating investigation investigations invisible invisibly invites invoke invoked invokes invoking involve involved involvement involves involving inward io iodide ion ionisation ionization ionize ionized ionizing ions ios ir irfs iron irradiated irradiation irradiations irreducible irregular irrelevant irreps irrespective irrotational is isentropic ism ismran iso isobar isocurvature isolate isolated isolates isolating isolation isomeric isomorphism isoscalar isospin isotensor isotope isotopes isotopic isotropic isotropically isotropy isovector isr isrf iss issue issued issues issuing isw iswrs iteration iterative iteratively its itself iv ivdm iwcd jbp jcap jet jets jetted jhep jittering jjem jlab jne job joint jointly journey jsns jump jumps junction juno just justify jwst jyfltrap kagra kaleidoscope kamiokande kamland kans kaon kaons karlsruhe kascade katrin kdar keep keeping keeps kekb kept kernel kernels kev key kg kgsc khz ki kick kicks kids kilograms kilometer kilometers kilonova kiloparsec kilotons kination kind kinds kinematic kinematical kinematically kinematics kinetic kinetically kinetics kink kinks kit kk kkl knee kno knockout knots knowledge known knt kpc kra krypton ksvz ksz kton kv kzm lab label labeled labelled labels laboratories laboratory lack lacking lacks ladder lag lags lake lambdacdm lamp land landmark landscape language lanthanide lanthanides lappd lappds lar large largely largeness larger largest lartpc lartpcs laser lasers last lasted lasting lat late latency latent later lateral laterally latest latitude latitudes latter lattice launch launched launching law laws lay layer layered layers layout lays lbl lbnf lbt lc lcdm lct ldf ldm ldmx ldpf le lead leadership leading leads leak leakage leaking learn learned learning learns least leave leaves leaving led ledger lee left legacy legend lehamoc length lengthens lengths lens lensed lensing lep leptogenesis leptohadronic lepton leptonic leptonically leptons leptophilic leptophobic leptoquark leptoquarks lesa less lesser lessons let letter level levels leverage leveraged leverages leveraging levitated lf lfbots lfu lfv lg lgi lgis lgrb lgrbs lhaaso lhc lhcb lhec libraries library lie lies lif life lifetime lifetimes lift lifted lifting lifts light lightcone lightcurve lighter lightest lightness lightweight ligo like likelihood likelihoods likely likewise lim limb limit limitation limitations limited limiting limits limr limrs line linear linearity linearized linearizing linearly lines link linked linking links liquid liquids lis lisa list listed lists litebird literature lithium lithospheric little littlest liv live lived lives livetime ll llagn llama llgrbs llms llp llps lm lma lmc ln lnc lngs lnv lo loaded loading lobes local localisation localised locality localization localizations localize localized localizing locally locate located location locations log logarithm logarithmic logarithmically logarithms logger logic logical long longer longevity longitude longitudinal longitudinally longstanding look looked looking looks loop loops loosening looser lore lorex lose losing loss losses lost loudest low lower lowered lowering lowers lowest lpbhs lpmt lpmts lq lqcd lqs lr lrd lrds lrf lrg lrgs lri lris lrsm ls lsnd lsp lss lsst lte luck lukewarm lumical luminosities luminosity luminous lunar lv lvk lwo lxe lying lz machine machines macropixel macrorealism macrorealistic macroscopic macroscopically mad made mads maestroex mafs mag magic magnet magnetar magnetars magnetic magnetically magnetised magnetism magnetization magnetizations magnetized magnetogenesis magnetohydrodynamic magnetohydrodynamical magnetohydrodynamics magnetorotational magnetorotationally magnetosonic magnetosphere magnetospheres magnetospheric magnets magnification magnified magnitude magnitudes main mainboard mainly maintain maintained maintaining maintains major majorana majority majoron make makes making mala mami manage manageable managed management mandatory mango manifest manifestation manifesting manifests manifold manner mantle manual manually manufacturer manufacturing manuscript many map mapped mapping mappings maps margin marginal marginalising marginalization marginalized marginalizing marginally mark marked markedly market marking marks marley mas masked masks masquerade mass masses massive massless master match matched matches matching material materials mathematical mathematically mathusla matrices matrix matter matters mature maturity mavan max maxi maxima maximal maximally maximization maximize maximized maximizes maximizing maximum may mb mbar mbf mbq mc mceq mcmc mcmf mcp mcps md mdom me mean meaning meaningful meaningfully means measurable measure measured measurement measurements measures measuring mec mecb mechanical mechanically mechanics mechanism mechanisms mechanistic media median mediate mediated mediates mediating mediation mediator mediators medium meerkat meet meeting meets meg megaelectronvolt megaparsecs member members membrane membranes memory mention mentioned merely merge merged merger mergers merging merit mesa mese mesh meson mesonic mesonless mesons messenger messengers met metacolor metal metallic metallicity metamodels metastability metastable meteorites meter meters method methodological methodologies methodology methods meticulous metric metrics mev mevprtl mfs mg mh mhd mhduet mhz mi mia mic micro microarcsecond microbial microboone microbubble microcalorimeter microcalorimeters microchannel microjy microlensing micrometers micron microphysical microphysics microquasar microquasars microscopic microscopy microseconds microstrips microwave mid middle might migration mild milder mildly milestone mill milliarcsecond millicharge millicharged millicharges millikelvin millimeter million millions millisecond milliseconds mimic mimicked mimicking mimics min mind miner mineral minerals minerva miniboone minifool minima minimal minimalistic minimality minimally minimization minimize minimized minimizes minimizing minimum minlo minor minos minus minute minutes mip mir mirror mirrored mirroring mirrors misaligned misalignment miscidynamic misconception misconceptions misestimate misidentification misleading mismatch mismodeling miss missed missing mission missions mit mitigate mitigated mitigates mitigating mitigation mix mixed mixes mixing mixings mixture mixtures mizar mk ml mle mlf mlfv mlrsm mm mma mnr mns mo mobile mock mocks mode model modeled modelers modeling modelled modelling models moderate moderately modern modes modest modestly modification modifications modified modifier modifies modify modifying mods modular modularized modulate modulated modulates modulation modulations module modules moduli modulus mojave molecular molecule molecules molybdenum moment momenta moments momentum mond mondian monitor monitored monitoring monitors monochromatic monoenergetic monojet monolithic monomial monophoton monopole monopoles monotonic monotonically month monthly months moo mops more moreover morphological morphologies morphology mos most mostly motion motions motivate motivated motivates motivating motivation motivations mound mountain mounting movable move moved moves moving mpe mpp mq mqs mr mrad mrc mrssm mrssmseesaw ms msc msm msps mssm mst msw mts much mucol multi multicomponent multidimensional multidisciplinary multifaceted multifrequency multilayer multimessenger multimessengers multimodal multinest multinucleon multipartite multiple multiplet multiplets multiplexed multiplexing multiplication multiplicative multiplicities multiplicity multiplied multiplies multiply multipmt multipole multipoles multiprobe multipurpose multiscale multivariate multiwavelength muography muon muonic muonium muonization muonphilic muons muonslab music must mutual mutually mux mw mysteries mystery na nacre nai naive name named namely nanograv nanohertz nanosecond nanoseconds narrow narrowband narrower narrows nasa nascent natal national native natural naturally naturalness nature navigating nb nbcs nbes nc nce ncteq nd ndaf ndafs ndgp ndi ndp near nearby nearest nearly neatly nebula nebulae nebular necessarily necessary necessitate necessitates necessitating necessity need needed needs negative negatively negativity neglect neglected neglecting neglects negligible negligibly neighbouring neither neon neos nested net network networks neural neut neutral neutralino neutralinos neutrino neutrinogenesis neutrinoless neutrinophilic neutrinophillic neutrinos neutrinosphere neutron neutronization neutrons never nevertheless new newborn newest newly nexo next ngc ngi ngis nh nhz niac nice nicely nicer nickel nicknamed nicu nid night nights nine ninja nitrogen njl nlo nlop nlsp nme nmes nmo nmr nmssm nn nnlo nnn nnns nnpdf nns nnvt no noble node nodes noise noisy nominal non nonadditive noncanonical noncommutative noncontact none nonequilibrium nonetheless nonextensive nonholomorphic noninertial nonleptonic nonlinear nonlinearity nonlocal nonlocality nonmagnetized nonminimal nonminimally nonobservation nonperturbative nonrelativistic nonresonant nonstandard nonstrange nonthermal nonthermally nontrivial nontrivially nonvanishing nonzero noon nor norm normal normalisation normalised normalization normalizations normalized normalizing normally north northern northwest not notable notably note notebook noted notes noteworthy notice noticeable noticeably notices noting notion notions notoriously nova novae novel novelty now np npdde npipe nr nre nreft ns nscool nsi nsis nsl nsms nss nu nubench nucdeex nuclear nucleation nuclei nucleon nucleonic nucleons nucleosynthesis nucleosynthetic nucleus nuclides nufit nugen nuggets nuglass nuisance nulib null number numbers numerical numerically numerous numi nuscope nuses nusol nustar nustorm nutev nutrig nuts nuwro nvidia nvss nw obey obeying obeys object objective objectives objects oblique obscure obscured obscuring observability observable observables observation observational observationally observations observatories observatory observe observed observer observers observes observing obtain obtained obtaining obtains occupancy occupation occupies occupy occur occurred occurrence occurrences occurring occurs ocean oct octant octet octonionic octupole od odd odds off offer offered offering offers official offline offloading offset offsets often oile old older olivine olographic ols om omilrec omit omitted omnifold omnilearned on onboard once one onemg ones ongoing online only onset onshore onto ontological opacities opacity opaque open opened opening openmp opens operability operate operated operates operating operation operational operationally operations operator operators opportunities opportunity opposed opposite oppositely optical optically optics optimal optimality optimally optimisation optimised optimistic optimization optimizations optimize optimized optimizing opting option options orbifold orbit orbital orbiting orbits orca order ordered ordering orderings orders ordinary organic organised organization organize organized organizing orientation orientations oriented origin original originally originate originated originates originating origins ornl orphan orthogonal orthogonality os oscillate oscillated oscillates oscillating oscillation oscillations oscillator oscillatory ot other others otherwise our out outburst outbursts outcome outcomes outdated outer outermost outflow outflows outgassing outgoing outline outlined outlines outlining outpace outperform outperforming outperforms output outputs outreach outside outskirts outstanding outward outwards ouv over overabundance overall overburden overburdens overcome overcoming overdensities overdensity overestimate overestimated overestimates overestimation overfitting overhead overlap overlapping overlaps overlook overlooked overproduce overproducing overproduction overshoot overshooting overtakes overview overwhelming owing own oxygen package packet packets paid pair paired pairing pairs pairwise paleodetectors palm pandax panels panoramic pantheonplus paper papers paradigm paradigms parallaxes parallel parallelizable parallels parameter parameterisation parameterisations parameterization parameterizations parameterize parameterized parameters parametric parametrically parametrisation parametrisations parametrization parametrizations parametrize parametrized paramount parasitic parent parity parsec parsecs part partial partially participants participate participated participating participation particle particles particlevit particular particularly particulars partly partner partners partnerships parton partonic partons parts pass passage passed passes passing passive past patches patchy path pathfinder pathfinders paths pathway pathways pattern patterns paucity pave paves paving pay payload payloads pbb pbf pbh pbhs pbr pbwo pc pchip pd pde pdf pdfs pdg pdhd pdmct pds pe peak peaked peaking peaks peculiar peculiarities peculiarity pedagogical pedestal penalties penalty pendulum penetrate penetrating penguin per percent percentage percentile perfect perfectly perform performance performances performed performing performs perhaps period periodic periodically periodicity periods permanent permeated permit permits permitted permutation perpendicular persist persisted persistence persistent persistently persisting persists personal perspective perspectives pertaining pertinent perturbation perturbations perturbative perturbatively perturbativity perturbed perturbs pessimistic petit pev pevatron pevatrons pevs pfs pg phantom phase phased phases phenomena phenomenological phenomenologically phenomenology phenomenon phonon phonons photocathode photodetector photodetectors photodisintegration photoelectron photoelectrons photohadronic photoluminescence photomeson photometric photometry photomultiplier photomultipliers photon photoneutron photons photonuclear photopion photoproduction photosensor photosensors photosphere photospheric physical physically physicists physics phz pic pico picture pieces pikachu pillar pilot pin pinching pingers pinn pinns pinpoint pion pioneer pioneered pioneering pionless pions pipe pipeline pipelines piston pitch pivot pivotal pixel pixelated pixels pixie pks pksz place placed placement places placing plan planar planck plane planes planet planetary planets planewave planned planning plans plant plants plasma plasmas plasmon plasmons plastic plate plateau plates platform platforms plausibility plausible plausibly play played playing plays plenoptic plethora plot plots plus pm pmn pmns pmt pmts png pngb pngbs pns pnss pockets poemma point pointed pointing pointings points pointwise poised polar polarimetric polarimetry polaris polarisation polarised polarizability polarization polarizations polarized pole poles policy polluted poloidal polon poltergeist polyharmonic polynomial polynomials pool poor poorer poorly popular populate populated population populations portability portable portal portals portion portions pose posed poses posited position positional positionally positioned positioning positions positive positively positivity positron positronium positrons possess possesses possessing possibilities possibility possible possibly post posterior posteriors postinflationary postmerger postulate postulated pot potential potentially potentials power powered powerful powering powers ppcge ppm ppq pq pr practical practically practice precede precedes preceding precessing precession precise precisely precision precisions preclude precludes precomputed precursor precursors predecessor predecessors predefined predict predictability predictable predicted predicting prediction predictions predictive predictivity predicts predominantly preface prefer preference preferences preferential preferentially preferred prefers preheating preliminary prem preons preparation preparatory prepare prepared prerequisite prescribed prescription prescriptions presence present presentation presentations presented presenting presently presents preserve preserved preserves preserving presolar pressing pressure pressures pressurized presumably presupernova pretrained prevalence prevalent prevent prevented preventing prevents previous previously price primaries primarily primary primat prime primordial principal principle principles prior priori prioritization prioritize priority priors prism pristine priya probabilistic probabilities probability probable probably probe probed probes probing problem problematic problems procedure procedures proceed proceeding proceedings proceeds process processed processes processing processor prodigious produce produced produces producing product production productions products profile profiled profiles profound progenitor progenitors progeny prograde program programme programs progress progresses progressively prohibitive prohibitively project projected projecting projection projections projects proliferated proliferation prolific prolonged prominence prominent promise promises promising promote promoted promotes promoting prompt prompted prompting promptly prone pronounced proof propagate propagated propagates propagating propagation propagator propagators proper properly properties property proportion proportional proportionally proportions proposal proposals propose proposed proposes proposing prospect prospective prospects protect protected protecting protection protects protocol protodune protodunes proton protoneutron protons protosolar prototype prototypes prototypical prototyping prove proved proven proves provide provided provides providing province proximity proxy ps psa psb psd pseudo pseudorapidities pseudorapidity pseudoscalar pseudoscalaron pseudoscalars pseudospin psr pt pta ptolemy ptp public publication publications publicly published pueo pull pulsar pulsars pulse pulsed pulser pulses punctuated pure purely purification purity purpose purposes pursue pursued pursuing pursuit pursuits push pushes pushing put putative puts putting puzzle puzzles puzzling pv pves pwn pwne pypi pythia python qcd qe qed qel qfd qfi qfim qft qfts qkes qlt qpe qsl qsls qso quadrant quadrants quadratic quadratically quadrature quadruple quadruplet quadrupolar quadrupole qualification qualitative qualitatively qualities quality quanta quantification quantified quantifies quantify quantifying quantisation quantitative quantitatively quantities quantity quantization quantize quantized quantum quanvolutional quark quarkonia quarkonium quarks quarkyonic quartet quartets quartic quartz quasar quasars quasiclassical quasielastic quasiparticle quasiparticles qubit qubits quench quenched quenching quest question questions quick quickly quiescent quiet quintessence quintessential quintet quintile quintom quintuplet quips quite quoted quotient qutrit qutrits raa radar radial radially radiate radiated radiates radiating radiation radiations radiative radiatively radii radio radioactive radioactivity radioastron radiochemical radiogenic radioisotopes radion radiopure radiopurity radius radon rainbow raise raised raises raising ram ramses random randomly range ranges ranging rank rapid rapidity rapidly rare rarely rarity rate rates rather ratio rational rationale ratios raw ray rays rcl rdwia reach reached reaches reaching reaction reactions reactor reactors read readily readiness reading readout readouts ready real realisation realisations realise realised realises realism realistic realistically reality realization realizations realize realized realizes realizing really realtime reanalyses reason reasonable reasonably reasoning reasons reassessment recalibration recall recast recasting recasts recedes receive received receiver receivers receives receiving recent recently recipe recode recognition recognize recognized recognizing recoil recoiling recoils recombination recommend recommendation recommended recompute reconcile reconciled reconciles reconciling reconnection reconsider reconstruct reconstructable reconstructed reconstructing reconstruction reconstructions reconstructs record recorded recording records recover recovered recovering recovers recovery recurrence recurrent recurring red redefinitions redesigning redirect redistribute redistributing redistribution redshift redshifted redshifts reduce reduced reduces reducing reduction reductions redundancy redundant reevaluate reexamine refer reference referred refers refine refined refinement refinements refines refining reflect reflectance reflected reflecting reflection reflections reflective reflectivity reflector reflects reformulate refraction refractive regard regarded regarding regardless regards regenerated regeneration regime regimes region regions register registered registration regression regular regularity regularization regularly regulate regulated regulates regulation regulator regulators reheat reheated reheating reinforce reinforced reinforcement reinforces reinteractions reinterpret reinterpretation reinterpretations reinterpreted reionisation reionization reject rejected rejecting rejection relate related relates relating relation relational relations relationship relationships relative relatively relativistic relativistically relativity relax relaxation relaxed relaxes relaxing release released releases relevance relevant reliability reliable reliably reliance reliant relic relics relied relies relieve relieved rely relying remain remained remaining remains remarkable remarkably reminiscent remnant remnants remote removal remove removed removes removing render rendered rendering renders rene renewed reno renormalisable renormalisation renormalizable renormalization renormalized reopens reorganize repeat repeated repeatedly repeating rephasing replace replaced replacement replaces replacing replenished replica replicate replicated reply report reported reports repository represent representation representations representative representatives represented representing represents reprocessed reprocessing reproduce reproduced reproduces reproducibility reproducible reproducing reproduction repulsive require required requirement requirements requires requiring requisite res resampling rescaled rescaling rescattering rescue research researchers resemble resembles resembling reservoir reservoirs reshape reshapes reshaping reside resides residing residual residuals residue residues resistant resistive resnet resolution resolutions resolvable resolve resolved resolves resolving resonance resonances resonant resonantly resort resource resources respect respecting respective respectively respects respond response responses responsible rest restful restore restored restores restoring restrict restricted restricting restriction restrictions restrictive restricts rests result resultant resulted resulting results resummation resummed retain retained retaining retains retraining retrograde return returned returns reusable reuse reusing revamped reveal revealed revealing reveals reversal reverse reverses review reviewed reviewing reviews revise revised revision revisit revisited revisiting revival revive revived revives revolution revolutionized revolutionizing reweighting rewritten rf rfi rfsoc rg rge rges rh rhf rhn rhns rho riaf rich richer richness riddle right rigid rigidity rigor rigorous rigorously rims ring rings rise rises rising risk rl rmf rms road roadmap robotic robust robustly robustness roc rock roi role roles roll rolling room root rooted roots rotate rotates rotating rotation rotational rotations rotator rotor rough roughly route routine routinely routines row rpa rpc rpcs rpv rs rsb rsd rsfp rsg rsgs rtx rubidium rule ruled rules ruling run runaway running runs runtime rxte sabs saddle sae safe safeguards safely safety sage said salient same sample sampled samples sampling samrai sane sapphire sasi satellite satellites satisfactorily satisfactory satisfied satisfies satisfy satisfying saturate saturated saturates saturating saturation say sb sbc sbi sbn sbnd sbo sbps scalability scalable scalar scalarization scalars scale scaled scales scaling scalings scan scanning scans scarcity scatter scattered scattering scatterings scatters scenario scenarios schedule scheduled scheduler scheduling schematic schematically scheme schemes science sciences scientific scientifically scientists scifi scintillating scintillation scintillator scintillators scoc scope score scores scotogenic scotoseesaw scratch screened screening screens scrutinize scrutinizing scrutiny scs sd sda sddm sdsde sdss se sea seafloor sealing seamless search searched searches searching season seasonal seasons seawater sec secluded second secondaries secondary seconds secret section sections sector sectorial sectors secular secure securely security sed sedimentation seds see seed seeds seek seeking seeks seem seemingly seems seen seesaw segment segmentation segmented segments seismic seismically seismological seismology select selected selecting selection selections selective selectively selects self semantic semiclassical semiconductor semiexclusive semileptonic sense sensei sensing sensitive sensitively sensitivities sensitivity sensor sensors sent separability separable separate separated separately separates separating separation separations separators sequence sequences sequential sequentially sequestered ser serendipitous serial series serious seriously serve served server serves services serving sesne set seti sets setting settings settling setup setups seven several severe severely sextet sf sfc sfermions sfho sfoewpt sfp sfr sfrds sgrb sgrbs sgw sgwb shadowing shall shallow shallower shape shaped shapefit shapes shaping share shared shares sharing sharp sharpen sharpens sharply sharpness shdm shear sheath shed shedding sheds sheet sheets shell shells sheltering shield shielding shields shift shifted shifter shifters shifting shifts shine ship shock shocked shocks shockwave shore short shortcoming shortcomings shorten shortened shorter shortly shot should show showcase showcasing showed shower showering showers showing shown shows shrinking shut shutoff shuts si sibyll side sideband sidereal siderius sides sidis sidm sight sigma sign signal signals signature signatures signed significance significances significant significantly signs silicon similar similarities similarity similarly simmering simple simpler simplest simplicity simplified simplifies simplify simplifying simplistic simply simulate simulated simulates simulating simulation simulations simulator simulators simultaneous simultaneously sin since sindrum sindy sine single singles singlet singlets singlino singly singular singularities singularity sink sipm sipms siren sirens sis sit site sites sits situ situated situation situations six sixteen sixth sixty sizable size sizeable sized sizes sk ska skao skeleton sketch sketches skin skins sky skymap skymaps slac sleptons slewing slice slight slightly slope slopes slow slower slowest slowly slows slq slqs slsne slt sly sm small smaller smallest smallness smbh smbhbs smbhs smd smearing smeft smm smoking smooth smoothed smoother smoothing smoothly smoothness smooths sms sn snappy snapshot snapshots snd sne sneutrino sneutrinos snewpy snia sno snolab snow snr snrs sns snsi sntools snu snwatch so soft soften softening softer softly software soho solar solder sole solely solid soliton solitons solution solutions solve solved solver solvers solves solving some sometimes somewhat sonic soon sophisticated sophistication sound source sourced sources sourcing south southern space spacecraft spaced spaces spacesim spacetime spacetimes spacing spad spallation span spanning spans sparse sparsely sparsepixels spatial spatially spatiotemporal speaking special specialized specially species specific specifically specification specifications specified specify specifying spectator spectra spectral spectrally spectrometer spectrometers spectrometry spectroscopic spectroscopy spectrum speculate speculation speculative speed speeds speedup speedups spend spent sphaleron sphalerons sphere spheres spherex spherical spherically spheroidal spider spike spikes spin spine spinning spinoptics spinor spinorial spinors spins spiral spirals spite spl spline splines split splits splitting splittings spmt spoil spoiling spontaneous spontaneously sporadic spot spots spread sps spt sptpol spurion spurions spurious sql square squared squark squarks squeezed squeezing squid sr src ss ssb ssd ssm sss stabilised stability stabilization stabilize stabilized stabilizes stabilizing stable stably stack stacked stacking stacks stage stages staging stainless stalled stalling stalls stand standalone standard standardizing standards standing standpoint stands star starburst starbursts stark stars start started starting starts stat state stated statement states static station stationary stations statistic statistical statistically statistics status stau staus stay stays stcf steadily steady steel steep steeper steeply steering stellar stem stemming stems step steps stereo stereoscopic sterile stfc stft stick stiff stiffness still stimulate stimulated stj stochastic stochasticity stone stop stopped stopping storage store stored straight straightforward straightforwardly strain strands strange strangeness strategic strategies strategy stratification stratified stratigraphy stratospheric stream streaming streams strength strengthen strengthening strengthens strengths stress stresses strict strictly strike striking string stringency stringent stringently strings stringy strip stripped strips strong stronger strongest strongly structural structurally structure structured structures struggle struts students studied studies study studying su sub subarray subclass subcomponent subcomponents subcritical subdetector subdominant subgrid subgroup subgroups subhalo subhaloes subject subjected subjet subleading sublimation subluminal submarines submergence submillimeter submission submitted submitting subnuclear subpercent subpopulations subprocess subsample subsequent subsequently subset subsidiary subsolar subspace substantial substantially substantive substrate substructure subsystem subsystems subthreshold subtle subtracted subtracting subtraction success successes successful successfully successive successor such sudden suffer suffers suffice sufficient sufficiently suggest suggested suggesting suggestive suggests suitability suitable suitably suite suited sulfate sum summaries summarise summarises summarize summarized summarizes summarizing summary summation summed summer summing sums sun super superallowed superb superburst superbursts superconducting superconductivity superconductor supercooled supercooling superem superfgd superfield superfields superfluid superfluidity supergiant supergiants supergravity superheavy superhorizon superimposed superior superkekb superluminal superluminous supermassive supernova supernovae superpartners superposed superposition superpositions superpotential superradiance superradiant superscaling supersede supersedes supersonic superspace supersymmetric supersymmetry supervised supplemental supplementary supplemented supplementing supplied supplies supply supplying support supported supporting supports supposed suppress suppressed suppresses suppressing suppression suppressions supranuclear suprathermal surf surface surfaces surpass surpasses surpassing surprising surprisingly surrogate surrogates surrounded surrounding surroundings surrounds survey surveys survival survive survives surviving susceptibility susceptible suspected sustain sustained sustaining susy svd svlbi sw swampland swap swapping sweep sweeper swgo swift sym symbiotic symbolic symmetric symmetries symmetrization symmetry synchronization synchronized synchrotron synergies synergistic synergy synthesis synthesised synthesize synthesized synthesizes synthesizing synthetic sys syst system systematic systematical systematically systematics systems sz tables tabulated tachocline tachyonic tackle tackled tackling tag tagged tagger tagging tail tailored tails take taken takes taking talk talks tambo tandem tangent tangle tank tanks tantalizing tao target targeted targeting targets tarot task tasks tau tauon taupolaris taus tbgs tbm tcp tdamm tdc tde tdes tdr teaching technical technically technique techniques technological technologies technology technosignature teleparallel telescope telescopes tell temperature temperatures template templates temporal temporally ten tend tendencies tendency tends tenet tens tension tensions tensor tensorflow tensors tentative tentatively teo term termed terminal terminate termination terms ternary terrain terrestrial territory tertiary tes tess test testability testable testbed tested testing tests tethered tetralepton tev texono text textbooks textual texture textures tfl than thanks that thawing thde the theia their them themselves then theorem theorems theoretic theoretical theoretically theories theorists theorized theory there thereby therefore therein thereof thermal thermalised thermalization thermalize thermalized thermally thermodynamic thermodynamical thermodynamics thermonuclear these thesis theta they thick thickness thin things third thirteen thirty this thorium thorough thoroughly those though thought thousand thousands thread three threefolds threshold thresholds through throughgoing throughout throughput throws thus tidal tied ties tight tighten tightened tightening tightens tighter tightest tightly tiles tilt time timelike timeline timely times timescale timescales timing timofey tiny tip tirl tl tm tmm tnr tnu to today tof together tolerance tomographic tomography ton tonne tonnes too took tool toolkit tools top topic topics topographic topological topologically topologies topology toponium toric toroidal torsion torsional torus total totally totd touch tov toward towards tower towers toy tpb tpc tpcs tpf tpr tpu tqft tqfts trace traced tracer tracers traces tracing track tracked tracker tracking tracks tractable traditional traditionally tradits trafficked train trained training trajectories trajectory transfer transferable transferred transferring transfers transform transformation transformational transformations transformative transformed transformer transformers transforming transforms transient transients transit transition transitional transitioning transitions transits translate translated translates translation transmission transmitted transmutation transonic transparency transparent transport transported transporting transrelativistic transverse trap trapped trapping travel traveled traveling travels traverse traversed traverses traversing treat treated treating treatment treatments treats tree trees tremendous trend trends trgb trial triality trials triangle triangles tribimaximal trident tries triga trigger triggered triggering triggers trigonometric trilepton trilinear trim trimaximal triorthogonal trios tripartite triple triplet triplets tristan tritium trivial true truly truncated truncation truth try ts tsz tube tubes tune tuned tunes tungsten tuning tunnel tunneling turbulence turbulent turn turned turning turnover turns tv twelve twenty twice twin two twofold txs ty type types typical typically uar ubiquitous ucmhs ufo ufos uhe uhecr uhecrs uk ula ulas ulb uldm ulsdm ultimate ultimately ultra ultrafast ultraheavy ultrahigh ultralight ultraluminous ultrapure ultrarelativistic ultrasat ultrasoft ultraviolet ulx ulxps ulxs unable unabsorbed unaccounted unaffected unambiguous unambiguously unanswered unattenuated unavailable unavoidable unavoidably unbiased unbind unbinned unbound unbounded unbroken uncalibrated uncertain uncertainties uncertainty unchanged uncharted unclear unconfined unconstrained uncontained unconventional uncorrelated uncoupled uncover uncovered uncovering uncovers under underdense underdensity underestimate underestimated underestimates underestimating underexplored undergo undergoes undergoing undergone undergraduate underground underlies underline underlines underlying underpin underpredicts underscore underscores underscoring undersea undershoot understand understanding understood undertaken underwater underway underwent undetectable undetected undetermined undine undoped unequal unexpected unexpectedly unexplained unexploited unexplored unflavored unflavoured unfold unfolded unfolding unidentifiable unidentified unification unified unifies uniform uniformity uniformly unify unifying unintegrated unique uniquely uniqueness unit unitarity unitary units unity universal universality universally universe unk unknown unknowns unlabeled unless unlike unlikely unlock unlocking unmagnetized unmeasured unmixed unmodeled unnatural unnaturally unnoticed unobservable unobserved unoscillated unpaired unparalleled unparticle unphysical unpolarized unprecedented unprecedentedly unraveling unreachable unrealistic unrealistically unrecognized unrelated unresolved unseen unsegmented unshocked unsolved unstable unsuccessful unsuppressed untapped untested until unusual unusually unveil unveiling unwanted upcoming upcs update updated updates updating upe upgoing upgrade upgraded upgrades upload upon upper upscaling upscatter upscattering upstream uptime upto upturn upward upwards uq uranium urca urgent us usa usable usage use used useful user users uses using usual usually utilising utility utilization utilize utilized utilizes utilizing utzt uv uvlf vacua vacuum valence valid validate validated validates validating validation validity valley valleys valuable value valued values vanilla vanish vanishes vanishing vanishingly vantage vapor variability variable variables variance variant variants variation variations varied varies varieties variety various vary varying vast vcc vch vd vecc vector vectorial vectorlike vectors velocities velocity vep ver verge verifiable verification verified verify veritas versa versatile version versions versus vertex vertical vertically vertices very vessel veto vetoes vetoing vev vevs vhe vi via viability viable vice vicinity view viewed viewing viewpoint views vigorous violate violated violates violating violation violations violent virial virtual virtually virtue viscosity viscous vish visibility visible visibly vision visualization visualize vit vital vl vlass vlba vlbi vlfm vll vlls vlm vlms vlq vlqs vmf vmp void voids volatile volcano voltage volume volumes von vortex vortices vpf vuv vvmfs vyper wakes wall walls warm warning warped was washed washout washouts water waterproof wave wavebands waveburst waveform waveforms wavefront wavefunction wavefunctions wavelength wavelengths wavenumber wavenumbers wavepid waves wavevector way ways wbls wc wcd wcda wcdm wcds wd wdm wds weak weaken weakened weakening weakens weaker weakest weakly wealth weather web website weeks weft weighing weight weighted weighting weights well wep were wgc what when whenever where whereas whereby wherein wherever whether which while whilst white who whole whose why wide wideband widely wider widespread width widths will wilson wimp wimps wind winding window windows winds wino wire wires wisdom wise with within without witness witnessed wl wls words work worked workflow workflows working workings works workshop world worldwide worse worsen worst worthy would write writing written wrong xenon xenonnt xgboost xlzd xp xrism year years yellow yet yield yielded yielding yields you young yps zenith zero zeros zi zone zones ztf".split(" "));
  var VOCAB_EPONYM = new Set("abell alamos amaterasu anderson android andromeda antarctic april argentina argo asimov askaryan atacama auger august baikal baksan bardeen bay bayes bayesian bell belle betti bhabha binocular birks bogoliubov boltzmann borealis borexino boulby brokdorf bronze brookhaven cabibbo carlo cas cassiopeia centaurus chandra chandrasekhar china chinese chooz circinus clifford coma cooper coulomb cowling cygnus daya democracy dicke dirac diracon doppler dvornikov eddington einstein eos euclid euler europe european explorer february fermi fermilab feynman figs fisher fock fornax fortran fourier france friedmann gaia garching gaussian geneva germany ghent gibbs glashow goldstone gompertzian grace gran greek green greenland gyr hamamatsu hamiltonian hamiltonians hartree hawking heisenberg hessian higgses hilbert hooft hubble huizhou ibn india indian injector institute italy jacobi jacobians james january japan jarlskog jefferson jiangmen jigsaw jinping jordan julia july june junior jupiter kamioka kaniadakis karlsruhe keplerian kerr koide korea laboratori lac lacertae lacs lagrangian lagrangians landau legendre leibstadt lindblad lindhard lorentz lorentzian los mach magellanic magnus mainz majorana march markarian markov mathematica maxwell mediterranean michel migdal milky minkowski monster monte moon morse mpc msun munich nab nancy nazionali neff neumann newtonian november oak october ohmic oph ophiuchi pacific palatini pamir pandora pantheon pauli penning perseus photonics phys pierre pino planck poisson pop primakoff princeton protvino quijote ref ricochet riemann roman rubin sanford sasso saturn schwarzschild schwinger september seyfert sibyll simons sirlin sitter skyrme sommerfeld soviet stodolsky subaru sudbury summit swift switzerland taishan thomson tibet tolman trinity tsallis turner university urca valencia vela venus vera virgo wasserstein webb weinberg western weyl whittaker wigner wilks witten zealand zee zwicky".split(" "));
  /* VOCAB:END */

  /* Name particles, and single initials. Both are shorter than the three
     letters the surname test asks for, so both used to fall through to the
     topic — and that is not a cosmetic loss: "de Salas neutrino" went to
     INSPIRE as `a Salas and ft de neutrino`, which searches for a different
     person AND puts INSPIRE's own date operator (`de`) inside a full-text
     clause. Measured on the live API: `a de Salas` answers 55 papers,
     `a Di Valentino` 935, `a E. Lisi` 239 against 174 for the old reading.

     A particle only counts as one when a name follows it — otherwise "de" in
     an English sentence would swallow the next word. */
  var PARTICLES = new Set((
    "de del della di da dal dalla do dos das du van von der den ter te " +
    "le la el al bin ibn ben mac mc o st saint san santa"
  ).split(" "));

  // Endings of common English and physics nouns and adjectives
  // ("determination", "measurement", "analysis", "phenomenological"). A
  // capitalised word with one of them is never guessed to be a surname, so the
  // rule needs no stop-list of every word a title can contain. Explicit
  // markers (author:, a:, by) are not subject to it.
  // Prefixes (particles, initials such as "E." or "A.M.") then a surname.
  var GLUED_NAME = /^(?:(?:[a-zà-ÿ'’]{1,5}\.?|(?:[a-z]\.){2,3})\s+){1,3}[a-zà-ÿ'’]{3,}(?:-[a-zà-ÿ'’]{2,})?$/i;
  var COMMON_END = /(?:tion|sion|ment|ysis|ity|ities|ing|ness|ics|ical|ous|ive|able|ally|ence|ance|ship|ology)s?$/i;
  // Plain English words a query is made of besides physics terms; never read
  // as a surname typed in lower case.
  var COMMON_WORDS = new Set((
    "data result results events event rate rates radiation light heavy dark " +
    "large small high low long short new old early late first second third " +
    "best other more less most least very only also same different " +
    "using use used based beyond within into over under between versus vs " +
    "effect effects case cases role status test tests probe probes hint hints " +
    "view look study studies work works way ways time times point points " +
    "range ranges value values parameter parameters number numbers"
  ).split(" "));
  // Words that open a query in sentence case without COMMON_END's endings;
  // only the FIRST word of a query is checked against them.
  var OPENERS = new Set((
    "new recent latest current future first final precise improved updated " +
    "global combined joint complete full novel possible general simple " +
    "review status results result search searches impact probing testing " +
    "constraints bounds limits evidence hints prospects towards toward " +
    "how what why which when where the a an on in of for from with using " +
    "light heavy large small high low long short next early late " +
    "neutrino neutrinos"
  ).split(" "));

  // Experiment names, recognised so that multi-word ones ("Daya Bay",
  // "Hyper-Kamiokande") survive as a single phrase instead of being split into
  // two capitalised words that then look like surnames.
  //
  // They are routed to the TOPIC field, not to `collaboration`. Typing "JUNO"
  // almost always means "papers about JUNO", whereas INSPIRE's `cn JUNO` means
  // "signed by the JUNO collaboration" — for a phenomenologist those are
  // disjoint sets, and the collaboration reading silently returns nothing.
  // Use the explicit c: prefix when you really want collaboration membership.
  var EXPERIMENTS = [
    "T2K", "NOvA", "DUNE", "JUNO", "Hyper-Kamiokande", "Super-Kamiokande",
    "IceCube", "KM3NeT", "KATRIN", "KamLAND", "KamLAND-Zen", "Daya Bay",
    "Double Chooz", "RENO", "Borexino", "SNO", "MINOS", "MicroBooNE",
    "SBND", "ICARUS", "LEGEND", "GERDA", "CUORE", "nEXO", "EXO-200",
    "ATLAS", "CMS", "LHCb", "ALICE", "Planck", "DESI", "Euclid", "SHiP"
  ];

  var NUMBER_WORDS = ["one", "two", "three", "four", "five", "six", "seven",
                      "eight", "nine", "ten"];

  function parseFree(raw) {
    var out = { author: [], title: "", topic: [], from: "", to: "", collab: "" };
    if (!raw) return out;
    var s = " " + raw.trim() + " ";

    // --- explicit field prefixes: a:  au:  author:  t:  title:  c:  ---
    s = s.replace(/\b(?:a|au|author)\s*[:=]\s*"([^"]+)"/gi, function (_, v) {
      out.author.push(v.trim()); return " ";
    });
    s = s.replace(/\b(?:a|au|author)\s*[:=]\s*(\S+)/gi, function (_, v) {
      out.author.push(v.trim()); return " ";
    });
    s = s.replace(/\b(?:t|ti|title)\s*[:=]\s*"([^"]+)"/gi, function (_, v) {
      out.title = v.trim(); return " ";
    });
    s = s.replace(/\b(?:c|cn|collab(?:oration)?)\s*[:=]\s*(\S+)/gi, function (_, v) {
      out.collab = v.trim(); return " ";
    });

    // --- quoted phrase becomes the title if none set yet ---
    s = s.replace(/"([^"]+)"/g, function (_, v) {
      if (!out.title) out.title = v.trim(); else out.topic.push(v.trim());
      return " ";
    });

    // --- date expressions, most specific first ---
    // 2019-2023  /  2019..2023  /  2019 to 2023  /  2019->2023
    //
    // The multi-character separators come FIRST in the alternation. With a
    // bare "-" first, "2024->2026" matched "-" and then failed on ">2026", the
    // range rule gave up, and the bare-year rule below silently kept only 2024
    // — a search for 2024–2026 quietly became a search for 2024 alone, in
    // every database at once. Arrow forms are worth accepting: this page's own
    // documentation shows INSPIRE's `de 2023->2025`, so people type it.
    s = s.replace(/\b(19|20)(\d{2})\s*(?:->|→|\.\.|–|—|-|to|through)\s*((?:19|20)\d{2})\b/gi,
      function (_, c, y, y2) {
        out.from = c + y; out.to = y2; return " ";
      });
    // since 2020 / after 2020 / from 2020
    s = s.replace(/\b(?:since|after|from|newer than)\s+((?:19|20)\d{2})\b/gi,
      function (_, y) { out.from = y; return " "; });
    // before 2015 / until 2015 / up to 2015
    s = s.replace(/\b(?:before|until|till|up to|older than)\s+((?:19|20)\d{2})\b/gi,
      function (_, y) { out.to = y; return " "; });
    // last N years / months
    // "last two years" is as natural as "last 2 years"; both are read.
    s = s.replace(/\blast\s+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(year|month)s?\b/gi,
      function (_, n, unit) {
        var k = /^\d+$/.test(n) ? parseInt(n, 10) : NUMBER_WORDS.indexOf(n.toLowerCase()) + 1;
        var d = new Date();
        if (/year/i.test(unit)) d.setFullYear(d.getFullYear() - k);
        else d.setMonth(d.getMonth() - k);
        out.from = d.toISOString().slice(0, 10);
        return " ";
      });
    // this year / last year
    s = s.replace(/\bthis year\b/gi, function () {
      out.from = String(new Date().getFullYear()); return " ";
    });
    s = s.replace(/\blast year\b/gi, function () {
      var y = new Date().getFullYear() - 1;
      out.from = String(y); out.to = String(y); return " ";
    });
    // month year  ->  from that month. Only real month names: "[a-z]*" after
    // the first three letters read "Marrone 2018" as March 2018 (and dropped
    // the author), "decay 2005" as December and "NOvA 2025" as November.
    s = s.replace(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(?:uary|ruary|ch|il|e|y|ust|t|tember|ober|ember)?\.?\s+((?:19|20)\d{2})\b/gi,
      function (_, mon, y) {
        var m = MONTHS[mon.toLowerCase().slice(0, 3)];
        out.from = y + "-" + String(m).padStart(2, "0");
        return " ";
      });
    // ISO dates
    s = s.replace(/\b((?:19|20)\d{2}-\d{2}(?:-\d{2})?)\b/g, function (_, d) {
      if (!out.from) out.from = d; else if (!out.to) out.to = d;
      return " ";
    });
    // a bare year
    s = s.replace(/\b((?:19|20)\d{2})\b/g, function (_, y) {
      if (!out.from) { out.from = y; out.to = y; }
      return " ";
    });

    /* --- identifiers: jump straight to the paper ---
       Both arXiv spellings, new (2107.00532) and old (hep-ph/0208026), and a
       DOI. Until this existed a pasted arXiv identifier produced NO INSPIRE
       query at all — the id is not a word, not a year and not a surname, so
       every branch dropped it and INSPIRE was simply not asked. */
    var ax = s.match(/\b(\d{4}\.\d{4,5})(v\d+)?\b/);
    if (!ax) ax = s.match(/\b([a-z-]{2,}(?:\.[A-Za-z]{2})?\/\d{7})(v\d+)?\b/);
    if (ax) { out.arxivId = ax[1]; s = s.replace(ax[0], " "); }
    var dx = s.match(/\b(10\.\d{4,9}\/[^\s"']+)/);
    if (dx) { out.doi = dx[1].replace(/[.,;]+$/, ""); s = s.replace(dx[0], " "); }

    // --- experiment names -> topic (see the note on EXPERIMENTS above) ---
    EXPERIMENTS.forEach(function (c) {
      // "Super-Kamiokande", "super kamiokande" and "superkamiokande" alike.
      var re = new RegExp("\\b" + c.replace(/[/\\^$*+?.()|[\]{}]/g, "\\$&")
                                    .replace(/[-\s]/g, "[-\\s]?") + "\\b", "i");
      if (re.test(s)) { out.topic.push(c); s = s.replace(re, " "); }
    });

    // --- remaining words: subject vocabulary -> topic, the rest -> surname ---
    var words = s.split(/\s+/).filter(Boolean);

    /* Glue a particle, or an initial, onto the name that follows it, before
       anything else looks at the list. Done here rather than inside the loop
       below because it is a fact about a PAIR of tokens, and the loop can
       only see one at a time. */
    function bare(t) { return String(t).toLowerCase().replace(/[.,;']+$/, ""); }
    // An initial needs its dot: a bare "a" or "A" is an article ("a
    // determination of ...") and must not be glued onto the next word.
    function isPrefix(t) {
      return PARTICLES.has(bare(t)) || /^(?:[a-z]\.){1,3}$/i.test(t);
    }
    // Any word the vocabulary knows is a topic: physics terms, search grammar,
    // plain English, and the words of real abstracts (VOCAB_*). What is left,
    // shaped like a name, is a surname — in whatever case it was typed.
    function known(b) {
      return PHYS.has(b) || DROP.has(b) || KIND.has(b) || OPENERS.has(b) ||
             COMMON_WORDS.has(b) || VOCAB_LOWER.has(b) || VOCAB_EPONYM.has(b) ||
             (b.length >= 7 && COMMON_END.test(b));   // not "King", "Ming"
    }
    // "Lisi", "dell'oro", "Gonzalez-Garcia": letters, at most one hyphen, and
    // no part the vocabulary knows ("long-baseline" is a topic).
    function isSurname(t) {
      var b = bare(t);
      if (!/^[a-zà-ÿ'’]{2,}(?:-[a-zà-ÿ'’]{2,})?[.,;]?$/i.test(t) || b.length < 3) return false;
      if (PARTICLES.has(b)) return false;
      return b.split("-").every(function (p) { return !known(p); });
    }
    // After an explicit `by` only the shape matters: "by Long" is a person.
    function nameShape(t) {
      var b = bare(t);
      return /^[a-zà-ÿ'’]{2,}(?:-[a-zà-ÿ'’]{2,})?$/i.test(b) && b.length >= 3 &&
             !PHYS.has(b) && !DROP.has(b) && !KIND.has(b) && !PARTICLES.has(b);
    }

    var glued = [];
    var wi = 0;
    while (wi < words.length) {
      // A RUN of prefixes, not one: "van der Meer" is two particles and a
      // name, and gluing only the last of them left `a Van der and a Meer`.
      var run = 0;
      while (isPrefix(words[wi + run]) && wi + run + 1 < words.length) run++;
      // The word behind the prefix must be a name ("E. Lisi", "de salas"):
      // "de" or "do" before an ordinary word are not particles.
      if (run && (isSurname(words[wi + run]) ||
                  (bare(words[wi - 1]) === "by" && nameShape(words[wi + run])))) {
        glued.push(words.slice(wi, wi + run + 1).join(" "));
        wi += run + 1;
      } else {
        // No name behind them, so they were never particles: "de" in an
        // English sentence must not swallow the word that follows.
        glued.push(words[wi]);
        wi++;
      }
    }
    words = glued;

    /* WHO IS AN AUTHOR:
         1. explicit: a:X  au:X  author:X (handled above), or names after `by`
            ("by Lisi", "by Marrone and Lisi");
         2. initials or a particle plus a surname ("E. Lisi", "a.m. marrone",
            "de Salas");
         3. any other word the vocabulary does not know and that is shaped
            like a name, in any case and at any position ("marrone solar
            neutrinos", "texture zeros huber", "Gonzalez-Garcia IceCube").
       Everything the vocabulary knows is the topic, capitalised or not
       ("Gallium anomaly", "Hubble tension", "matter effects in the Earth"). */
    function addAuthor(name) { if (out.author.length < 4) out.author.push(capitalise(name)); }

    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      var clean = w.replace(/^[.,;("']+|[.,;)"']+$/g, "");
      if (!clean) continue;
      var lower = clean.toLowerCase();

      // `by` opens a list of names; it ends at the first word that is not one.
      if (lower === "by" && i + 1 < words.length) {
        var j = i + 1, took = 0;
        while (j < words.length) {
          var nm = words[j].replace(/^[.,;("']+|[.,;)"']+$/g, "");
          if (!(nameShape(nm) || GLUED_NAME.test(nm))) break;
          addAuthor(nm); took++;
          var more = /,$/.test(words[j]) ||
                     (j + 2 < words.length && /^(?:and|&)$/i.test(words[j + 1]));
          j += /,$/.test(words[j]) ? 1 : (more ? 2 : 1);
          if (!more) break;
        }
        if (took) { i = j - 1; continue; }
      }

      if (DROP.has(lower)) continue;
      if (KIND.has(lower)) { out.topic.push(lower); continue; }
      if (PHYS.has(lower)) { out.topic.push(clean); continue; }

      // A glued "E. Lisi" / "de Salas" carries a space; INSPIRE takes both
      // spellings as written (verified).
      var glued2 = /\s/.test(clean) &&
                   GLUED_NAME.test(clean) &&
                   !/\d/.test(clean);
      if (glued2 || isSurname(clean)) addAuthor(clean);
      else out.topic.push(clean);
    }

    return out;
  }

  // "lisi" -> "Lisi", "van der waals" left alone if already mixed case.
  // "e. lisi" -> "E. Lisi", "a.m. marrone" -> "A.M. Marrone", "de salas" ->
  // "de Salas": initials upper case, particles kept as typed.
  function capitalise(s) {
    if (s !== s.toLowerCase()) return s;          // user typed some capitals
    return s.split(" ").map(function (p, i, all) {
      if (/^(?:[a-z]\.)+$/.test(p)) return p.toUpperCase();
      if (i < all.length - 1 && PARTICLES.has(p)) return p;
      return p.charAt(0).toUpperCase() + p.slice(1);
    }).join(" ");
  }

  /* ---------------------------------------------------------------
     2. Sync parsed fields into the visible inputs
     --------------------------------------------------------------- */

  var userTouched = {};
  ["author", "title", "topic", "from", "to", "collab"].forEach(function (k) {
    var el = $("#q-" + k);
    if (el) el.addEventListener("input", function () { userTouched[k] = true; });
  });

  // The last reading of the free-text line, kept so `fields()` can carry the
  // identifiers it found. Everything else the reader can correct in a box;
  // an arXiv id or a DOI has no box, and is a fact about the query.
  var lastParsed = null;

  function applyParse() {
    var p = parseFree(elFree.value);
    lastParsed = p;
    if (!userTouched.author) elAuthor.value = p.author.join("; ");
    if (!userTouched.title)  elTitle.value  = p.title;
    if (!userTouched.topic)  elTopic.value  = p.topic.join(" ");
    if (!userTouched.from)   elFrom.value   = p.from;
    if (!userTouched.to)     elTo.value     = p.to;
    syncTime(p);
    if (!userTouched.collab) elCollab.value = p.collab;
    renderChips(p);
    return p;
  }

  /* The "time" choice in the advanced options is a shortcut for the From and
     To boxes, not a second source of truth: it writes into them and the rest
     of the page reads only them. A date written in the query line wins over
     the shortcut (and flips it to "custom", which is what it is). */
  function yearsAgo(n) {
    var d = new Date();
    d.setFullYear(d.getFullYear() - n);
    return d.toISOString().slice(0, 10);
  }

  function syncTime(p) {
    if (!elTime) return;
    if (p && (p.from || p.to)) { elTime.value = "custom"; return; }
    var n = parseInt(elTime.value, 10);
    if (n && !userTouched.from && !userTouched.to) {
      elFrom.value = yearsAgo(n);
      elTo.value = "";
    }
  }

  if (elTime) {
    elTime.addEventListener("change", function () {
      var n = parseInt(elTime.value, 10);
      if (n) {
        elFrom.value = yearsAgo(n); elTo.value = "";
        userTouched.from = userTouched.to = true;
      } else if (elTime.value === "any") {
        elFrom.value = ""; elTo.value = "";
        userTouched.from = userTouched.to = true;
      } else if (elFrom) elFrom.focus();
      renderChips(null);
    });
    [elFrom, elTo].forEach(function (el) {
      if (el) el.addEventListener("input", function () { elTime.value = "custom"; });
    });
  }

  function renderChips(p) {
    var bits = [];
    if (elAuthor.value) bits.push(["Author", elAuthor.value]);
    if (elTitle.value)  bits.push(["Title", elTitle.value]);
    if (elTopic.value)  bits.push(["Topic", elTopic.value]);
    if (elCollab.value) bits.push(["Collaboration", elCollab.value]);
    if (elFrom.value || elTo.value) {
      bits.push(["Dates", (elFrom.value || "…") + " → " + (elTo.value || "…")]);
    }
    if (p && p.arxivId) bits.push(["arXiv ID", p.arxivId]);
    if (p && p.doi) bits.push(["DOI", p.doi]);
    elChips.innerHTML = bits.length
      ? bits.map(function (b) {
          return '<span class="chip"><span class="chip__k">' + esc(b[0]) +
                 '</span>' + esc(b[1]) + "</span>";
        }).join("")
      : '<span class="muted small">Nothing recognised yet — type a query above.</span>';
  }

  elFree.addEventListener("input", function () {
    userTouched = {};
    applyParse();
  });
  ["author", "title", "topic", "from", "to", "collab"].forEach(function (k) {
    var el = $("#q-" + k);
    if (el) el.addEventListener("input", function () { renderChips(null); });
  });

  /* ---------------------------------------------------------------
     3. Query builders, one per backend
     --------------------------------------------------------------- */

  function fields() {
    return {
      author: elAuthor.value.split(";").map(function (s) { return s.trim(); }).filter(Boolean),
      title: elTitle.value.trim(),
      topic: elTopic.value.trim(),
      collab: elCollab.value.trim(),
      from: elFrom.value.trim(),
      to: elTo.value.trim(),
      // Carried from the free-text line, not from a box: an identifier is
      // something the reader pasted, never something they refined by hand.
      arxivId: lastParsed && lastParsed.arxivId,
      doi: lastParsed && lastParsed.doi,
      // What the DATABASES are asked for, which is not the same question as
      // how the answer is displayed. Only the date axis is worth pushing
      // upstream: asking for the most recent records genuinely changes which
      // twenty come back. Citations are not pushed — see the note above
      // SORTS — and neither is a subfield, which no database indexes the way
      // this page groups it.
      sort: sortKey === "date" ? "date" : "relevance"
    };
  }

  function yearOf(s) { var m = /^(\d{4})/.exec(s || ""); return m ? m[1] : ""; }

  // INSPIRE's query language is strict about operators. Verified behaviour:
  //   a <name>            author            works
  //   t "<phrase>"        title phrase      works
  //   cn <name>           collaboration     works
  //   ft <words>          full text         works, forgiving — use for topics
  //   de 2019->2023 / de > 2019 / de < 2015  date ranges
  // Chaining several `t <word>` with AND is far too strict (usually 0 hits),
  // so free keywords go through `ft` instead.
  /* TWO BARE WORDS ARE TWO QUESTIONS, and INSPIRE answers only one of them.
     "lisi marrone" means two authors — `a Lisi and a Marrone`, 120 papers.
     "antonio marrone" means one person — `a Antonio Marrone`, 133 papers.
     Nothing in the two strings tells them apart, and the WRONG reading does
     not degrade, it returns exactly zero: `a Antonio and a Marrone` is 0 hits,
     `a Lisi Marrone` is 0 hits (verified live, 2026-09-12). So a reader
     searching their own name got no INSPIRE results at all, and the page
     filled up with whatever the generic databases had — which is how this was
     noticed.

     INSPIRE takes parentheses and `or`, so both readings go in ONE query and
     the database decides. The clauses that are not about authors are repeated
     inside each branch, because `or` binds looser than `and` and a trailing
     date clause would otherwise apply to the second reading only. */
  function inspireQuery(f) {
    /* An identifier names ONE paper, so it is the whole question: no author,
       no date, nothing to loosen. Both spellings answer exactly one record
       (verified live). Before this, a pasted arXiv id produced no INSPIRE
       query at all and a DOI went through as a bare word. */
    var ids = [];
    if (f.arxivId) ids.push("arxiv " + f.arxivId);
    if (f.doi) ids.push("doi " + f.doi);
    if (ids.length) return ids.join(" or ");

    var rest = [];
    if (f.title) rest.push('t "' + f.title + '"');
    if (f.collab) rest.push("cn " + f.collab);
    // Topic terms: BARE when they are the whole query, `ft` otherwise.
    // Verified live, both ways: "lecture notes string theory" bare returns
    // the Les Houches notes ranked by true relevance, while the ft version
    // matches any long review that cites lecture notes and, sorted by
    // citations, buried the target under Quantum Entanglement; but
    // "a Feruglio and modular forms" bare (or with abs/parentheses) is 0
    // hits — with an author clause only `ft` combines. Date clauses chain
    // fine with bare terms (also verified).
    if (f.topic) {
      rest.push((f.author.length || rest.length) ? "ft " + f.topic : f.topic);
    }
    if (f.from && f.to) rest.push("de " + yearOf(f.from) + "->" + yearOf(f.to));
    else if (f.from) rest.push("de > " + yearOf(f.from));
    else if (f.to) rest.push("de < " + yearOf(f.to));

    if (!f.author.length) return rest.join(" and ");

    var apart = f.author.map(function (a) { return "a " + a; });
    // Only two single words are ambiguous. One name is unambiguous, three or
    // more are surnames in practice, and a name the reader already wrote in
    // full ("Antonio Marrone" in the author box, or a:"Antonio Marrone")
    // contains a space and is left exactly as typed.
    var ambiguous = f.author.length === 2 &&
                    !/\s/.test(f.author[0]) && !/\s/.test(f.author[1]);
    if (!ambiguous) return apart.concat(rest).join(" and ");

    var asTwo = apart.concat(rest).join(" and ");
    var asOne = ["a " + f.author[0] + " " + f.author[1]].concat(rest).join(" and ");
    return "(" + asTwo + ") or (" + asOne + ")";
  }

  /* A pasted identifier is a request for ONE paper, and the generic
     databases cannot take it as a search term: asked for "2107.00532" they
     fall back on their default subject and answer with forty unrelated
     neutrino papers, which is worse than answering nothing. So each builder
     below says whether it can answer an identifier exactly, and returns null
     when it cannot. A null means the source is skipped for that search and
     the status line counts one database fewer — visible, and true. */
  function idOnly(f) {
    return !!(f.arxivId || f.doi) &&
           !f.author.length && !f.title && !f.topic && !f.collab;
  }

  // arXiv registers its own DOI with DataCite under this prefix, which is how
  // an arXiv identifier becomes something DataCite can match exactly.
  function arxivDoi(id) { return "10.48550/arXiv." + id; }

  function crossrefUrl(f) {
    var p = new URLSearchParams();
    if (idOnly(f)) {
      // Crossref registers journal DOIs, never arXiv's own: with only an
      // arXiv id there is nothing here to ask for.
      if (!f.doi) return null;
      p.set("filter", "doi:" + f.doi);
      p.set("rows", "5");
      p.set("select", "title,author,issued,container-title,DOI,URL,type,subject,abstract");
      p.set("mailto", "antonio.marrone@ba.infn.it");
      return "https://api.crossref.org/works?" + p.toString();
    }
    var bib = [f.title, f.topic, f.collab].filter(Boolean).join(" ");
    if (bib) p.set("query.bibliographic", bib);
    if (f.author.length) p.set("query.author", f.author.join(" "));
    var filt = [];
    if (f.from) filt.push("from-pub-date:" + padDate(f.from, true));
    if (f.to) filt.push("until-pub-date:" + padDate(f.to, false));
    if (filt.length) p.set("filter", filt.join(","));
    p.set("rows", "20");
    p.set("select", "title,author,issued,container-title,DOI,URL,type,subject,abstract");
    p.set("sort", f.sort === "date" ? "published" : "relevance");
    p.set("order", "desc");
    p.set("mailto", "antonio.marrone@ba.infn.it");
    return "https://api.crossref.org/works?" + p.toString();
  }

  function padDate(s, isStart) {
    if (/^\d{4}$/.test(s)) return s + (isStart ? "-01-01" : "-12-31");
    if (/^\d{4}-\d{2}$/.test(s)) return s + (isStart ? "-01" : "-28");
    return s;
  }

  function openalexUrl(f) {
    var p = new URLSearchParams();
    if (idOnly(f)) {
      // Verified: OpenAlex matches a journal DOI and does NOT match arXiv's
      // 10.48550 one.
      if (!f.doi) return null;
      p.set("filter", "doi:" + f.doi);
      p.set("per-page", "5");
      p.set("mailto", "antonio.marrone@ba.infn.it");
      return "https://api.openalex.org/works?" + p.toString();
    }
    var search = [f.title, f.topic, f.collab].filter(Boolean).join(" ");
    if (search) p.set("search", search);
    // Physical Sciences only (domain 3 in OpenAlex's topic hierarchy —
    // verified live: "string theory" drops from every field of knowledge to
    // 367k physics records). OpenAlex indexes everything; this page is on a
    // physics site and marketing papers matching the word "theory" are how
    // a search for lecture notes once returned the Theory of Planned
    // Behaviour.
    var filt = ["primary_topic.domain.id:3"];
    if (f.author.length) {
      filt.push("raw_author_name.search:" + f.author.join(" "));
    }
    if (f.from) filt.push("from_publication_date:" + padDate(f.from, true));
    if (f.to) filt.push("to_publication_date:" + padDate(f.to, false));
    p.set("filter", filt.join(","));
    p.set("per-page", "20");
    p.set("sort", f.sort === "date" ? "publication_date:desc" : "relevance_score:desc");
    p.set("mailto", "antonio.marrone@ba.infn.it");
    return "https://api.openalex.org/works?" + p.toString();
  }

  function arxivUrl(f) {
    var terms = [];
    f.author.forEach(function (a) { terms.push("au:" + quote(a)); });
    if (f.title) terms.push("ti:" + quote(f.title));
    if (f.topic) f.topic.split(/\s+/).forEach(function (w) { terms.push("all:" + w); });
    if (f.collab) terms.push("all:" + quote(f.collab));
    var q = terms.join(" AND ") || "all:neutrino";
    var p = new URLSearchParams({ searchtype: "all", query: q });
    if (f.from) p.set("start_date", padDate(f.from, true));
    if (f.to) p.set("end_date", padDate(f.to, false));
    return "https://arxiv.org/search/?" + p.toString();
  }

  function quote(s) { return /\s/.test(s) ? '"' + s + '"' : s; }

  /* arXiv, reached through DataCite rather than through arXiv's own API.
     Not a workaround for its own sake: export.arxiv.org sends no
     Access-Control-Allow-Origin header, so a browser refuses to read the
     response and the search would simply never return. arXiv registers a DOI
     for every preprint with DataCite (the 10.48550/arXiv.* prefix, client
     `arxiv.content`), and DataCite's API does send CORS and needs no key —
     so this is arXiv's own metadata, deposited by arXiv, fetched from where
     the browser is allowed to read it. */
  /* DataCite runs Elasticsearch query_string, where + - = && || > < ! ( ) { }
     [ ] ^ " ~ * ? : \ / all mean something. Any of them arriving from the free
     text turns a good search into zero results with a cheerful HTTP 200 — no
     error, just nothing — so they are stripped before the query is assembled. */
  function esClean(s) {
    return String(s || "").replace(/[+\-=&|!(){}\[\]^"~*?:\\\/<>]/g, " ")
                          .replace(/\s+/g, " ").trim();
  }

  function dataciteUrl(f) {
    if (idOnly(f)) {
      var p0 = new URLSearchParams();
      p0.set("query", 'doi:"' + (f.doi || arxivDoi(f.arxivId)) + '"');
      p0.set("page[size]", "5");
      return "https://api.datacite.org/dois?" + p0.toString();
    }
    var terms = [];
    f.author.forEach(function (a) {
      var v = esClean(a);
      if (v) terms.push("creators.name:(" + v + ")");
    });
    if (esClean(f.title)) terms.push('titles.title:("' + esClean(f.title) + '")');
    if (esClean(f.topic)) terms.push("(" + esClean(f.topic) + ")");
    if (esClean(f.collab)) terms.push('("' + esClean(f.collab) + '")');
    var q = terms.join(" AND ") || "neutrino";
    if (f.from || f.to) {
      q += " AND publicationYear:[" + (yearOf(f.from) || "1900") +
           " TO " + (yearOf(f.to) || "2100") + "]";
    }
    var p = new URLSearchParams();
    p.set("query", q);
    p.set("client-id", "arxiv.content");
    p.set("page[size]", "20");
    p.set("sort", f.sort === "date" ? "created" : "relevance");
    return "https://api.datacite.org/dois?" + p.toString();
  }

  /* DataCite carries arXiv's subject headings as prose with the category
     identifier in brackets — "High Energy Physics - Experiment (hep-ex)",
     under subjectScheme "arXiv". The bracket is the part that means
     something; the prose is the same string in every record. Anything
     deposited under another scheme (DataCite adds "FOS: Physical sciences")
     is not an arXiv category and is left alone. */
  function arxivSubjects(list) {
    var out = [];
    (list || []).forEach(function (x) {
      if (!x || String(x.subjectScheme || "").toLowerCase() !== "arxiv") return;
      var m = /\(([a-z-]+(?:\.[a-z-]+)?)\)\s*$/i.exec(String(x.subject || ""));
      if (m && out.indexOf(m[1].toLowerCase()) === -1) out.push(m[1].toLowerCase());
    });
    return out;
  }

  function dataciteAbstract(list) {
    var ds = (list || []).filter(Boolean);
    var ab = ds.filter(function (x) { return x.descriptionType === "Abstract"; })[0];
    return ((ab || ds[0]) || {}).description || "";
  }

  function fromArxiv(f) {
    return getJSON(dataciteUrl(f)).then(function (d) {
      return (d.data || []).map(function (r) {
        var a = r.attributes || {};
        var doi = (a.doi || "");
        // 10.48550/arxiv.2608.01890 -> 2608.01890
        var id = (/arxiv\.(.+)$/i.exec(doi) || [])[1] || "";
        var issued = (a.dates || []).filter(function (x) {
          return x.dateType === "Issued";
        })[0];
        return {
          source: "arXiv",
          date: (issued && String(issued.date).slice(0, 10)) ||
                (a.publicationYear ? a.publicationYear + "-01-01" : ""),
          title: ((a.titles || [])[0] || {}).title || "(untitled)",
          authors: (a.creators || []).slice(0, 6).map(function (c) {
            return c.name || [c.givenName, c.familyName].filter(Boolean).join(" ");
          }),
          more: (a.creators || []).length > 6,
          year: a.publicationYear || "",
          journal: "arXiv" + (id ? ":" + id : ""),
          arxiv: id,
          cats: arxivSubjects(a.subjects),
          abstract: plain(dataciteAbstract(a.descriptions)),
          keywords: (a.subjects || []).map(function (x) { return x && x.subject; })
                                      .filter(Boolean),
          links: compact([
            id && { label: "arXiv", href: "https://arxiv.org/abs/" + id },
            id && { label: "PDF", href: "https://arxiv.org/pdf/" + id },
            doi && { label: "DOI", href: "https://doi.org/" + doi }
          ])
        };
      });
    });
  }

  function adsUrl(f) {
    var parts = [];
    f.author.forEach(function (a) { parts.push('author:"' + a + '"'); });
    if (f.title) parts.push('title:"' + f.title + '"');
    if (f.topic) parts.push("abs:(" + f.topic + ")");
    if (f.collab) parts.push('abs:"' + f.collab + '"');
    if (f.from || f.to) {
      parts.push("year:[" + (yearOf(f.from) || "1900") + " TO " +
                 (yearOf(f.to) || "9999") + "]");
    }
    return "https://ui.adsabs.harvard.edu/search/q=" +
           encodeURIComponent(parts.join(" ") || "neutrino");
  }

  function scholarUrl(f) {
    var p = new URLSearchParams();
    p.set("q", [f.title, f.topic, f.collab].filter(Boolean).join(" ") || "neutrino");
    if (f.author.length) p.set("as_sauthors", f.author.join(" "));
    if (yearOf(f.from)) p.set("as_ylo", yearOf(f.from));
    if (yearOf(f.to)) p.set("as_yhi", yearOf(f.to));
    return "https://scholar.google.com/scholar?" + p.toString();
  }

  /* ---------------------------------------------------------------
     4. Fetching and normalising
     --------------------------------------------------------------- */

  function getJSON(url, opts) {
    var ctl = new AbortController();
    var t = setTimeout(function () { ctl.abort(); }, 20000);
    return fetch(url, Object.assign({ signal: ctl.signal }, opts || {}))
      .then(function (r) {
        clearTimeout(t);
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      });
  }

  /* ---------------------------------------------------------------
     Asking INSPIRE, and not taking silence for an answer

     Two ways this database used to disappear from a page, both seen for
     real:

       * a MOMENTARY failure. `a Salas and ft de neutrino` answered HTTP 500
         once and then 308 hits three times in a row — a transient, and there
         was no retry, so the one database this page trusts most simply was
         not in the results and nothing said why;
       * a query that is merely too NARROW. INSPIRE does not degrade when a
         reading is wrong or a filter too tight: it returns zero. A date
         range that excludes the paper, a topic word the record does not
         carry, a title phrase spelled differently — each gives an empty
         answer that looks exactly like "this does not exist".

     So: one retry on a transport failure, and then a ladder. The rungs drop
     the most disposable constraint first — dates, then the topic, then the
     title when an author is there to carry the search — and the first rung
     that answers wins. The reader is told when a looser question was the one
     that answered, because "INSPIRE found nothing" and "INSPIRE found
     nothing until the dates came off" are different facts.
     --------------------------------------------------------------- */

  var INSPIRE_FIELDS =
    "titles,authors,arxiv_eprints,publication_info,earliest_date," +
    "dois,citation_count,control_number,inspire_categories," +
    "abstracts,keywords,collaborations";
  var LADDER_MAX = 4;          // the question plus three loosenings
  var inspireLoosened = "";        // which constraint had to go, if any

  function looser(f) {
    var g = {
      author: f.author, title: f.title, topic: f.topic, collab: f.collab,
      from: f.from, to: f.to, sort: f.sort, arxivId: f.arxivId, doi: f.doi
    };
    // An identifier is already the narrowest possible question and there is
    // nothing to loosen: zero hits means INSPIRE does not have that paper.
    if (f.arxivId || f.doi) return null;
    if (g.from || g.to) { g.from = ""; g.to = ""; g.why = "the date range"; return g; }
    /* Then the LAST name, and before the topic, because a word mistaken for
       a surname is the commonest way a query comes back empty: the parser
       has to guess which leftover words are people, and one wrong guess is
       fatal rather than merely noisy — `a Bilenky and a Petcov and a Massive
       and ft neutrinos` answers 0, the same query without "Massive" answers
       12 (measured). Dropping the word beats moving it into the topic, which
       only relocates the problem: a word the records do not carry zeroes the
       search from there too (verified: 0 either way for an invented one). */
    if (g.author.length > 1) {
      g.author = g.author.slice(0, -1);
      g.why = "the last name, “" + f.author[f.author.length - 1] + "”";
      return g;
    }
    if (g.topic) { g.topic = ""; g.why = "the topic words"; return g; }
    if (g.title && (g.author.length || g.collab)) {
      g.title = ""; g.why = "the title words"; return g;
    }
    return null;
  }

  function inspireOnce(f) {
    var q = inspireQuery(f);
    if (!q) return Promise.resolve(null);
    var p = new URLSearchParams({
      q: q, size: "20", page: "1", fields: INSPIRE_FIELDS
    });
    // Relevance mode leaves INSPIRE's own ranking alone: sort=mostcited
    // turned every topic search into "the most cited papers that mention
    // these words", which for "lecture notes string theory" was Quantum
    // Entanglement and the PDG Review.
    if (f.sort === "date") p.set("sort", "mostrecent");
    return getJSON("https://inspirehep.net/api/literature?" + p.toString());
  }

  function inspireTry(f) {
    return inspireOnce(f).then(null, function () { return inspireOnce(f); });
  }

  function inspireLadder(f, depth) {
    return inspireTry(f).then(function (d) {
      var hits = (d && d.hits && d.hits.hits) ? d.hits.hits : [];
      if (hits.length) return hits;
      if (depth + 1 >= LADDER_MAX) return hits;
      var g = looser(f);
      if (!g) return hits;
      return inspireLadder(g, depth + 1).then(function (more) {
        if (more.length && !inspireLoosened) inspireLoosened = g.why;
        return more;
      });
    });
  }

  function fromInspire(f) {
    return inspireLadder(f, 0)
      .then(function (hits) {
        return hits.map(function (h) {
          var m = h.metadata || {};
          var pi = (m.publication_info || [])[0] || {};
          var journal = pi.journal_title
            ? pi.journal_title + (pi.journal_volume ? " " + pi.journal_volume : "") +
              (pi.year ? " (" + pi.year + ")" : "")
            : "";
          var ep = (m.arxiv_eprints || [])[0];
          return {
            source: "INSPIRE-HEP",
            date: m.earliest_date || (pi.year ? pi.year + "-01-01" : ""),
            title: (m.titles || [{}])[0].title || "(untitled)",
            authors: (m.authors || []).slice(0, 6).map(function (a) {
              return a.full_name;
            }),
            more: (m.authors || []).length > 6,
            year: pi.year || (m.earliest_date || "").slice(0, 4),
            journal: journal,
            citations: m.citation_count,
            citeFrom: typeof m.citation_count === "number" ? CITE_SOURCE : "",
            abstract: plain(((m.abstracts || [])[0] || {}).value),
            keywords: (m.keywords || []).map(function (k) { return k && k.value; })
                                        .filter(Boolean),
            collabs: (m.collaborations || []).map(function (c) { return c && c.value; })
                                             .filter(Boolean),
            // Both classifications INSPIRE holds: the arXiv categories the
            // preprint was deposited under, and INSPIRE's own subject terms
            // (Phenomenology-HEP, Experiment-HEP, Astrophysics, …), which are
            // the only ones a record with no eprint carries.
            cats: (ep && ep.categories) || [],
            inspireCats: (m.inspire_categories || []).map(function (c) {
              return c.term;
            }),
            links: compact([
              ep && { label: "arXiv:" + ep.value, href: "https://arxiv.org/abs/" + ep.value },
              (m.dois || [])[0] && { label: "DOI", href: "https://doi.org/" + m.dois[0].value },
              { label: "INSPIRE", href: "https://inspirehep.net/literature/" + m.control_number }
            ])
          };
        });
      });
  }

  function fromCrossref(f) {
    var url = crossrefUrl(f);
    if (!url) return Promise.resolve([]);
    return getJSON(url).then(function (d) {
      return ((d.message && d.message.items) || []).map(function (it) {
        var dp = (it.issued && it.issued["date-parts"] && it.issued["date-parts"][0]) || [];
        return {
          source: "Crossref",
          date: dp.length
            ? dp[0] + "-" + String(dp[1] || 1).padStart(2, "0") +
              "-" + String(dp[2] || 1).padStart(2, "0")
            : "",
          title: (it.title || ["(untitled)"])[0],
          authors: (it.author || []).slice(0, 6).map(function (a) {
            return [a.given, a.family].filter(Boolean).join(" ");
          }),
          more: (it.author || []).length > 6,
          year: it.issued && it.issued["date-parts"] &&
                it.issued["date-parts"][0] ? it.issued["date-parts"][0][0] : "",
          journal: (it["container-title"] || [])[0] || it.type || "",
          // Present only when the publisher deposited it, which for physics
          // journals is most of the time not at all. Free when it is there.
          crSubjects: it.subject || [],
          abstract: plain(it.abstract),        // JATS markup when present
          links: compact([
            it.DOI && { label: "DOI", href: "https://doi.org/" + it.DOI }
          ])
        };
      });
    });
  }

  function fromOpenAlex(f) {
    var url = openalexUrl(f);
    if (!url) return Promise.resolve([]);
    return getJSON(url).then(function (d) {
      return (d.results || []).map(function (w) {
        var loc = w.primary_location || {};
        return {
          source: "OpenAlex",
          date: w.publication_date ||
                (w.publication_year ? w.publication_year + "-01-01" : ""),
          title: w.title || w.display_name || "(untitled)",
          authors: (w.authorships || []).slice(0, 6).map(function (a) {
            return a.author && a.author.display_name;
          }),
          more: (w.authorships || []).length > 6,
          year: w.publication_year || "",
          journal: (loc.source && loc.source.display_name) || "",
          citations: w.cited_by_count,
          // OpenAlex classifies every work in a four-level hierarchy
          // (domain > field > subfield > topic). The topic is the useful
          // level — "Neutrino Physics Research" is a topic, while its
          // subfield is the much coarser "Nuclear and High Energy Physics".
          topic: (w.primary_topic && w.primary_topic.display_name) || "",
          topicField: (w.primary_topic && w.primary_topic.subfield &&
                       w.primary_topic.subfield.display_name) || "",
          abstract: invertedAbstract(w.abstract_inverted_index),
          keywords: (w.keywords || []).concat(w.topics || [])
                      .map(function (k) { return k && k.display_name; })
                      .filter(Boolean),
          links: compact([
            w.doi && { label: "DOI", href: w.doi },
            loc.landing_page_url && { label: "Publisher", href: loc.landing_page_url }
          ])
        };
      });
    });
  }

  /* Semantic Scholar, keyless Graph API with fieldsOfStudy=Physics. The
     shared anonymous pool rate-limits aggressively (HTTP 429); the failure
     is reported like any other source and the search still answers from the
     rest. */
  function s2Url(f) {
    // Semantic Scholar's search endpoint takes words, not identifiers, and
    // its by-identifier endpoint answers a different shape; rather than feed
    // it an id it cannot use, this source sits the search out.
    if (idOnly(f)) return null;
    var q = [f.title, f.topic, f.collab].filter(Boolean).join(" ");
    if (f.author.length) q = (q ? q + " " : "") + f.author.join(" ");
    var p = new URLSearchParams();
    p.set("query", q || "neutrino");
    p.set("fieldsOfStudy", "Physics");
    p.set("fields", "paperId,title,authors,year,publicationDate,venue," +
                    "externalIds,citationCount,s2FieldsOfStudy,abstract");
    p.set("limit", "20");
    if (yearOf(f.from) || yearOf(f.to)) {
      p.set("year", (yearOf(f.from) || "") + "-" + (yearOf(f.to) || ""));
    }
    return "https://api.semanticscholar.org/graph/v1/paper/search?" + p.toString();
  }

  function fromS2(f) {
    var url = s2Url(f);
    if (!url) return Promise.resolve([]);
    return getJSON(url).then(function (d) {
      return (d.data || []).map(function (w) {
        var ext = w.externalIds || {};
        return {
          source: "Semantic Scholar",
          date: w.publicationDate || (w.year ? w.year + "-01-01" : ""),
          title: w.title || "(untitled)",
          authors: (w.authors || []).slice(0, 6).map(function (a) { return a.name; }),
          more: (w.authors || []).length > 6,
          year: w.year || "",
          journal: w.venue || "",
          citations: w.citationCount,
          abstract: plain(w.abstract),
          s2fields: (w.s2FieldsOfStudy || []).map(function (x) {
            return x && x.category;
          }).filter(Boolean),
          links: compact([
            ext.ArXiv && { label: "arXiv", href: "https://arxiv.org/abs/" + ext.ArXiv },
            ext.DOI && { label: "DOI", href: "https://doi.org/" + ext.DOI },
            w.paperId && { label: "Semantic Scholar",
                           href: "https://www.semanticscholar.org/paper/" + w.paperId }
          ])
        };
      });
    });
  }

  function compact(a) { return a.filter(Boolean); }

  // Abstracts arrive as plain text (INSPIRE, Semantic Scholar, DataCite) or
  // as JATS/HTML markup (Crossref, sometimes INSPIRE): tags out, spaces tidy.
  function plain(s) {
    return String(s == null ? "" : s).replace(/<[^>]+>/g, " ")
                                     .replace(/\s+/g, " ").trim();
  }

  // OpenAlex ships abstracts as {word: [positions]} for licensing reasons.
  function invertedAbstract(ix) {
    if (!ix || typeof ix !== "object") return "";
    var words = [];
    Object.keys(ix).forEach(function (w) {
      (ix[w] || []).forEach(function (i) { words[i] = w; });
    });
    return words.filter(Boolean).join(" ");
  }

  /* ---------------------------------------------------------------
     Sanity filters on what the databases return
     --------------------------------------------------------------- */

  // Crossref carries records "issued" in 2114. With the date sort those
  // float above every real paper, so an implausible year loses its date and
  // sinks instead.
  var THIS_YEAR = new Date().getFullYear();
  function plausibleYear(y) {
    y = parseInt(y, 10);
    return y >= 1800 && y <= THIS_YEAR + 1;
  }
  function saneDates(r) {
    if (r.date && !plausibleYear(r.date.slice(0, 4))) r.date = "";
    if (r.year && !plausibleYear(r.year)) r.year = "";
    return r;
  }

  // INSPIRE and arXiv are physics by construction; Crossref and OpenAlex
  // index every field of knowledge and their relevance ranking returns
  // anything containing one query word ("theory" -> Theory of Planned
  // Behaviour). In BROAD mode a record that ONLY generic databases returned
  // must show the substantive query terms in its title or venue: all of them
  // for short queries, all but one when four or more.
  var PHYSICS_NATIVE = { "INSPIRE-HEP": 1, "arXiv": 1, "Semantic Scholar": 1 };
  function passesTermGate(r, terms) {
    if (!terms.length) return true;
    var hay = " " + normTitle(r.title + " " + (r.journal || "")) + " ";
    var hit = terms.filter(function (t) {
      return hay.indexOf(" " + t + " ") > -1 || hay.indexOf(t) > -1;
    }).length;
    var need = terms.length >= 4 ? terms.length - 1 : terms.length;
    return hit >= need;
  }
  function gateTerms(f) {
    return normTitle(f.topic + " " + f.title).split(" ")
      .filter(function (t) { return t.length >= 3 && !DROP.has(t); });
  }

  /* ---------------------------------------------------------------
     PRECISE mode: a strong match for EVERY record

     Broad mode trusts the physics-native databases (INSPIRE, arXiv, Semantic
     Scholar) to have returned only relevant records, and that trust is what
     lets a NASA paper about Jupiter's magnetosphere come back for "JUNO
     oscillation": Semantic Scholar's "Physics" field includes planetary
     physics, and its ranking needs one matching word. Precise mode asks the
     RECORD to show the query, in the text the databases give for free:
     title, abstract, subject keywords and collaboration field.

     The rule is the old one — every substantive term for up to three terms,
     all but one for four or more — applied to that larger text, so a paper
     titled "... double ... decay" whose abstract says "neutrinoless double
     beta" is kept. It is not applied to:

       * author-only queries (no topic or title words): nothing to match;
       * identifier queries (an arXiv id or a DOI): the identifier IS the
         match, and gating the one record asked for would be absurd.

     Terms match on the start of a word after a crude stem (symmetry /
     symmetries, neutrino / neutrinos), never in the middle of one.
     --------------------------------------------------------------- */

  var mode = "precise";           // "precise" | "broad"

  function stemOf(t) {
    if (t.length < 5 || /ss$/.test(t)) return t;
    var u = t.replace(/(?:ies|y|es|s)$/, "");
    return u.length >= 3 ? u : t;
  }

  function preciseText(r) {
    return " " + normTitle([r.title, r.abstract || "",
                            (r.keywords || []).join(" "),
                            (r.collabs || []).join(" ")].join(" ")) + " ";
  }

  function hasTerm(hay, t) { return hay.indexOf(" " + stemOf(t)) > -1; }

  /* Ambiguous experiment names.

     "JUNO" is a reactor-neutrino detector in Jiangmen AND a NASA probe at
     Jupiter AND a goddess; "NOvA" is an experiment and a stellar explosion;
     "DUNE" is a landscape feature. A name alone cannot separate them and the
     databases, ranking by word, do not try. So for each name that can be
     confused there are

       ctx   words one of which must appear in the title, abstract or
             keywords for the record to count as being about the experiment
             (or the experiment must be named in the collaboration field);
       neg   words that betray the other meaning. Precise mode already
             rejects a record without context, so these decide nothing on
             their own; they are what the live check (tools/search_live_check.js)
             uses to flag a top-ranked result as suspect.

     Matching is case-insensitive and on whole words (an optional plural
     ending allowed), for the query as well as for the record. */
  var ENTITIES = {
    "JUNO": {
      ctx: ["neutrino", "antineutrino", "reactor", "oscillation", "Jiangmen",
            "liquid scintillator", "mass ordering", "mass hierarchy",
            "photomultiplier", "geoneutrino"],
      neg: ["Jupiter", "spacecraft", "magnetosphere", "Juno mission", "Jovian",
            "goddess", "NASA", "Juno spacecraft", "Jupiter's"]
    },
    "T2K": {
      ctx: ["neutrino", "antineutrino", "oscillation", "Tokai", "Kamioka",
            "long-baseline", "accelerator", "J-PARC", "Super-Kamiokande"],
      neg: []
    },
    "NOvA": {
      ctx: ["neutrino", "antineutrino", "oscillation", "NuMI", "Fermilab",
            "long-baseline", "appearance", "far detector", "mass ordering"],
      neg: ["novae", "supernova remnant", "stellar explosion", "white dwarf",
            "classical nova", "recurrent nova", "thermonuclear"]
    },
    "DUNE": {
      ctx: ["neutrino", "oscillation", "LBNF", "Fermilab", "liquid argon",
            "long-baseline", "far detector", "Sanford"],
      neg: ["sand dune", "sand dunes", "aeolian", "desert", "sand"]
    },
    "KATRIN": {
      ctx: ["neutrino", "tritium", "beta decay", "spectrometer", "neutrino mass",
            "endpoint"],
      neg: []
    },
    "Borexino": {
      ctx: ["neutrino", "solar", "scintillator", "Gran Sasso", "geoneutrino",
            "antineutrino", "CNO"],
      neg: []
    },
    "IceCube": {
      ctx: ["neutrino", "South Pole", "Cherenkov", "astrophysical", "muon",
            "high-energy", "cosmic ray", "detector"],
      neg: ["ice cube tray", "ice cubes"]
    },
    "KamLAND": {
      ctx: ["neutrino", "antineutrino", "reactor", "geoneutrino", "scintillator",
            "Kamioka", "double beta"],
      neg: []
    },
    "Daya Bay": {
      ctx: ["neutrino", "antineutrino", "reactor", "oscillation", "theta13",
            "Guangdong", "mixing angle"],
      neg: ["bay area", "fishing", "tourism"]
    },
    "SNO": {
      ctx: ["neutrino", "solar", "heavy water", "Sudbury", "deuterium",
            "oscillation", "scintillator", "charged current"],
      neg: ["snow", "snowfall", "snowpack"]
    },
    "MINOS": {
      ctx: ["neutrino", "oscillation", "NuMI", "Fermilab", "long-baseline",
            "Soudan", "muon neutrino"],
      neg: ["Minos myth", "Crete", "Minoan", "labyrinth", "Minotaur", "myth"]
    },
    "PINGU": {
      ctx: ["neutrino", "IceCube", "mass ordering", "mass hierarchy",
            "oscillation", "atmospheric", "South Pole"],
      neg: ["penguin", "Pingu the penguin"]
    },
    "ORCA": {
      ctx: ["neutrino", "KM3NeT", "mass ordering", "mass hierarchy",
            "oscillation", "atmospheric", "Mediterranean", "Cherenkov"],
      neg: ["orca whale", "killer whale", "whale", "whales", "cetacean",
            "Orcinus", "dolphin"]
    },
    "ANTARES": {
      ctx: ["neutrino", "telescope", "Mediterranean", "Cherenkov", "KM3NeT",
            "muon", "high-energy", "Toulon"],
      neg: ["star Antares", "rocket", "red supergiant", "Alpha Scorpii",
            "Scorpius", "Antares rocket"]
    }
  };

  function wordRe(w) {
    var esc1 = String(w).trim().replace(/[-/\\^$*+?.()|[\]{}]/g, "\\$&")
                        .replace(/\s+/g, "\\s+");
    return new RegExp("(?:^|[^a-z0-9])" + esc1 + "(?:s|es)?(?![a-z0-9])", "i");
  }
  var ENTITY_RE = {};
  Object.keys(ENTITIES).forEach(function (k) {
    ENTITY_RE[k] = {
      name: wordRe(k),
      ctx: ENTITIES[k].ctx.map(wordRe),
      neg: ENTITIES[k].neg.map(wordRe)
    };
  });

  // The ambiguous names the QUERY mentions, as topic, title or collaboration.
  function queryEntities(f) {
    var q = [f.topic, f.title, f.collab].join(" ");
    return Object.keys(ENTITIES).filter(function (k) {
      return ENTITY_RE[k].name.test(q);
    });
  }

  /* A context word that is ALSO one of the query's own terms proves little
     when it is a generic one: "JUNO oscillation" asks for "oscillation", so
     finding it in a paper about the oscillation of Jupiter's magnetosphere
     is not evidence of the experiment. Such words (the list below) count only
     when the query did not ask for them; "neutrino", "reactor", "Jiangmen"
     and the like count always, because no other meaning of the name shares
     them. */
  var WEAK_CTX = ["oscillation", "oscillations", "detector", "accelerator", "muon",
                  "solar", "atmospheric", "telescope", "high-energy", "long-baseline",
                  "appearance", "spectrometer", "endpoint", "far detector",
                  "cosmic ray", "astrophysical", "Cherenkov"].map(function (w) {
    return w.toLowerCase();
  });

  function entityOk(r, k, terms) {
    var re = ENTITY_RE[k];
    var text = [r.title, r.abstract || "", (r.keywords || []).join(" ")].join(" ");
    if ((r.collabs || []).some(function (c) { return re.name.test(c); })) return true;
    var asked = terms.map(stemOf);
    // A record that says nothing of the experiment's own context is not
    // about the experiment, whether or not it also shows a negative cue.
    return ENTITIES[k].ctx.some(function (word, i) {
      var low = word.toLowerCase();
      if (WEAK_CTX.indexOf(low) > -1 && asked.indexOf(stemOf(normTitle(low))) > -1) return false;
      return re.ctx[i].test(text);
    });
  }

  function strongMatch(r, f, terms, ents) {
    if (f.arxivId || f.doi) return true;
    var units = terms.slice();
    var hay = preciseText(r);
    var need, hit;
    if (!units.length && !f.collab) return true;       // author-only query
    hit = units.filter(function (t) { return hasTerm(hay, t); }).length;
    if (f.collab) {
      units.push(normTitle(f.collab));
      if (hay.indexOf(" " + normTitle(f.collab) + " ") > -1 ||
          hay.indexOf(" " + normTitle(f.collab)) > -1) hit++;
    }
    need = units.length >= 4 ? units.length - 1 : units.length;
    if (hit < need) return false;
    return ents.every(function (k) { return entityOk(r, k, terms); });
  }

  /* ---------------------------------------------------------------
     Deduplication across databases
     The same paper usually comes back from all three. Merge on DOI,
     then arXiv id, then a normalised title, keeping every source and
     every link.
     --------------------------------------------------------------- */

  function normTitle(s) {
    return String(s || "").toLowerCase()
      .replace(/\$[^$]*\$/g, " ")          // strip inline maths
      .replace(/[^a-z0-9]+/g, " ")
      .replace(/^the\s+/, "")             // "The unfinished fabric" = "Unfinished fabric"
      .trim();
  }

  function keyOf(r) {
    var doi = "";
    var arx = "";
    r.links.forEach(function (l) {
      if (/doi\.org\//i.test(l.href)) doi = l.href.replace(/^.*doi\.org\//i, "").toLowerCase();
      if (/arxiv\.org\/abs\//i.test(l.href)) arx = l.href.replace(/^.*abs\//i, "").replace(/v\d+$/, "");
    });
    /* The arXiv identifier FIRST, not the DOI. The same paper reaches this
       page as a preprint and as an article, and those two records carry
       DIFFERENT dois — arXiv's own 10.48550/arXiv.NNNN on one, the journal's
       on the other — so keying on the doi kept them apart while the arXiv id
       they share would have joined them. Seen for real: pasting an arXiv id
       returned the same paper twice, once from INSPIRE and once from arXiv.
       Two different papers never share an arXiv id, so this cannot merge
       what should stay apart. */
    return (arx && "arxiv:" + arx) || doi || "t:" + normTitle(r.title);
  }

  /* Subject information is per-database and none of them has it all:
     INSPIRE knows the arXiv categories and its own subject terms, OpenAlex
     knows its topic, Semantic Scholar its fields of study, Crossref whatever
     the publisher deposited. A merged record must keep every one of them, or
     the subfield of a paper would depend on which database happened to be
     first in the list rather than on what is known about the paper. */
  var TAG_LISTS = ["cats", "inspireCats", "s2fields", "crSubjects"];
  var COPY_LISTS = TAG_LISTS.concat(["links", "authors", "keywords", "collabs"]);

  /* The merge works on COPIES. It is run again over every row received so far
     each time one more database answers, and a merge that edited its input
     (sources appended, links pushed) would see the edited rows on the next
     pass and double-count what it had already folded in. */
  function cloneRow(r) {
    var c = Object.assign({}, r);
    COPY_LISTS.forEach(function (k) { if (c[k]) c[k] = c[k].slice(); });
    return c;
  }

  // The text the databases hold for free: the longest abstract wins, keyword
  // and collaboration lists are united.
  function mergeText(target, other) {
    if ((other.abstract || "").length > (target.abstract || "").length) {
      target.abstract = other.abstract;
    }
    ["keywords", "collabs"].forEach(function (k) {
      if (!other[k] || !other[k].length) return;
      var have = target[k] || [];
      var low = have.map(function (x) { return String(x).toLowerCase(); });
      other[k].forEach(function (v) {
        if (v && low.indexOf(String(v).toLowerCase()) === -1) {
          have.push(v); low.push(String(v).toLowerCase());
        }
      });
      target[k] = have;
    });
  }

  /* A count from INSPIRE always wins, whichever record happened to lead the
     merge. Without this the number depended on the order the databases
     answered in: the same paper showed 93 from INSPIRE or 147 from OpenAlex
     depending on which one had led. See the note above `fillCitations`. */
  function mergeCitations(target, other) {
    if (other.citeFrom === CITE_SOURCE) {
      target.citations = other.citations;
      target.citeFrom = other.citeFrom;
      return;
    }
    if (target.citeFrom === CITE_SOURCE) return;
    if (typeof target.citations !== "number" && typeof other.citations === "number") {
      target.citations = other.citations;
    }
  }

  function mergeTags(target, other) {
    TAG_LISTS.forEach(function (k) {
      if (!other[k] || !other[k].length) return;
      var have = target[k] || [];
      other[k].forEach(function (v) {
        if (v && have.indexOf(v) === -1) have.push(v);
      });
      target[k] = have;
    });
    if (!target.topic && other.topic) target.topic = other.topic;
    if (!target.topicField && other.topicField) target.topicField = other.topicField;
  }

  function mergeAll(groups) {
    var byKey = {};
    var order = [];
    groups.forEach(function (g) {
      g.rows.forEach(function (r0) {
        var k = keyOf(r0);
        var r = r0;
        if (!byKey[k]) {
          r = cloneRow(r0);
          r.sources = [r.source];
          byKey[k] = r;
          order.push(k);
          return;
        }
        var t = byKey[k];
        if (t.sources.indexOf(r.source) === -1) t.sources.push(r.source);
        // keep the richest metadata
        if (!t.journal && r.journal) t.journal = r.journal;
        if (!t.date && r.date) t.date = r.date;
        mergeCitations(t, r);
        mergeTags(t, r);
        mergeText(t, r);
        if (r.authors.length > t.authors.length) { t.authors = r.authors; t.more = r.more; }
        r.links.forEach(function (l) {
          var seen = t.links.some(function (x) {
            return x.href.replace(/^https?:\/\//, "") === l.href.replace(/^https?:\/\//, "");
          });
          if (!seen) t.links.push(l);
        });
      });
    });
    return mergeByTitle(order.map(function (k) { return byKey[k]; }));
  }

  /* Second pass, on the title alone.
     The identifier pass above cannot catch everything: the same paper often
     carries the JOURNAL doi in one database and arXiv's own 10.48550 doi in
     another, so the two records get different keys and both survive. That is
     how "Updated bounds on the (1, 2) neutrino oscillation parameters" came
     back twice, once as "(1, 2)" and once as "(1,2)". normTitle already
     flattens punctuation, so a title pass merges them — and it runs second, so
     a matching identifier still takes precedence over a coincidence of words. */
  function mergeByTitle(rows) {
    var byTitle = {};
    var out = [];
    rows.forEach(function (r) {
      var t = normTitle(r.title);
      // Very short titles are not distinctive enough to merge on.
      if (!t || t.length < 25) { out.push(r); return; }
      var first = byTitle[t];
      if (!first) { byTitle[t] = r; out.push(r); return; }
      r.sources.forEach(function (s) {
        if (first.sources.indexOf(s) === -1) first.sources.push(s);
      });
      if (!first.journal && r.journal) first.journal = r.journal;
      if (!first.date && r.date) first.date = r.date;
      mergeCitations(first, r);
      mergeTags(first, r);
      mergeText(first, r);
      if (r.authors.length > first.authors.length) {
        first.authors = r.authors; first.more = r.more;
      }
      r.links.forEach(function (l) {
        var seen = first.links.some(function (x) {
          return x.href.replace(/^https?:\/\//, "") === l.href.replace(/^https?:\/\//, "");
        });
        if (!seen) first.links.push(l);
      });
    });
    return out;
  }

  /* ---------------------------------------------------------------
     Match classification
     Buckets, strongest first. What the reader wants to know is not
     which database answered but *why* this paper came back.
     --------------------------------------------------------------- */

  var BUCKETS = [
    { id: "exact",   label: "Exact title match",
      note: "The title you asked for." },
    { id: "authors", label: "All authors present",
      note: "Every surname you listed appears among the authors." },
    { id: "some",    label: "Some authors present",
      note: "At least one of the surnames you listed, but not all." },
    { id: "topic",   label: "Subject match only",
      note: "Matched on topic, title words or collaboration — none of your authors." }
  ];

  function surnameOf(name) {
    var n = String(name || "").trim();
    if (n.indexOf(",") > -1) return n.split(",")[0].trim().toLowerCase();
    var parts = n.split(/\s+/);
    return (parts[parts.length - 1] || "").toLowerCase();
  }

  function classify(r, f) {
    if (f.title) {
      var a = normTitle(r.title), b = normTitle(f.title);
      if (a === b || (b.length > 12 && a.indexOf(b) > -1)) return "exact";
    }
    if (!f.author.length) return "topic";

    var have = r.authors.map(surnameOf);
    var hit = 0;
    f.author.forEach(function (want) {
      var w = surnameOf(want);
      if (have.some(function (h) { return h === w || h.indexOf(w) === 0; })) hit++;
    });
    if (hit === 0) return "topic";
    return hit === f.author.length ? "authors" : "some";
  }

  /* ---------------------------------------------------------------
     Citations come from INSPIRE, and from nowhere else

     Every database here counts citations, and they do not agree — the same
     paper is 93 at INSPIRE, a different number at OpenAlex, a third at
     Semantic Scholar, because they index different literature. Mixed into one
     column those numbers are not comparable, and the "Citations" sort stops
     meaning anything: it would rank a paper high for being indexed by the
     most generous counter rather than for being used. For high-energy physics
     INSPIRE is the count the field actually quotes, so it is the only one
     this page shows.

     Two consequences, both deliberate:

       * a record INSPIRE returned carries INSPIRE's number, whichever
         database led the merge (see `mergeCitations`);
       * a record INSPIRE did NOT return is looked up here, by arXiv id or
         DOI, in one extra request per twenty records. INSPIRE answers 20
         results per search, so a paper it knows perfectly well is often
         simply not among the twenty it sent back — dropping its count for
         that reason would be an artefact of the page size, not a fact about
         the paper.

     What no lookup finds keeps NO count at all rather than borrowing one:
     an empty cell is honest, a foreign number wearing INSPIRE's meaning is
     not. Such a record sorts as unknown, which puts it at the bottom in both
     directions — the same rule undated records follow.

     With INSPIRE unticked in "Search in", no count is shown anywhere: the
     reader has asked not to use the one source this page trusts for them.
     --------------------------------------------------------------- */

  var CITE_SOURCE = "INSPIRE-HEP";
  var CITE_BATCH = 20;          // ids per lookup request
  var CITE_MAX_REQUESTS = 3;    // never more than 60 records looked up

  // The identifier INSPIRE can be asked by. arXiv first: it is the one a
  // preprint always has, and it needs no escaping. A DOI may contain
  // brackets (10.1007/JHEP09(2020)178) — verified to work as written.
  function citeTerm(r) {
    var doi = "", arx = "";
    (r.links || []).forEach(function (l) {
      if (!arx && /arxiv\.org\/abs\//i.test(l.href)) {
        arx = l.href.replace(/^.*abs\//i, "").replace(/v\d+$/, "");
      }
      if (!doi && /doi\.org\//i.test(l.href)) {
        doi = l.href.replace(/^.*doi\.org\//i, "");
      }
    });
    if (arx) return { term: "arxiv " + arx, key: arx.toLowerCase() };
    if (doi) return { term: "doi " + doi, key: doi.toLowerCase() };
    return null;
  }

  /* What an earlier lookup learned, per search: a number, or false for "INSPIRE
     does not know it". Redrawing after a change of mode or discipline then
     costs no request for a record that was already looked up. */
  var citeCache = {};

  // Citations a record carries from any database other than INSPIRE are
  // removed; what the cache knows from INSPIRE is put back. Synchronous, so a
  // redraw while the lookup is still on its way never shows a foreign number.
  function citesFromCache(rows) {
    rows.forEach(function (r) {
      if (r.citeFrom !== CITE_SOURCE) delete r.citations;
      if (r.citeFrom === CITE_SOURCE) return;
      var t = citeTerm(r);
      if (t && typeof citeCache[t.key] === "number") {
        r.citations = citeCache[t.key];
        r.citeFrom = CITE_SOURCE;
      }
    });
  }

  function fillCitations(rows, useInspire) {
    citesFromCache(rows);
    if (!useInspire) return Promise.resolve();

    var want = [];
    rows.forEach(function (r) {
      if (r.citeFrom === CITE_SOURCE) return;
      var t = citeTerm(r);
      if (t && !(t.key in citeCache)) want.push({ row: r, term: t.term, key: t.key });
    });
    if (!want.length) return Promise.resolve();

    var batches = [];
    for (var i = 0; i < want.length; i += CITE_BATCH) {
      if (batches.length >= CITE_MAX_REQUESTS) break;
      batches.push(want.slice(i, i + CITE_BATCH));
    }

    return Promise.all(batches.map(function (b) {
      var p = new URLSearchParams({
        q: b.map(function (x) { return x.term; }).join(" or "),
        size: String(b.length),
        fields: "citation_count,dois,arxiv_eprints"
      });
      return getJSON("https://inspirehep.net/api/literature?" + p.toString())
        .then(function (d) {
          var by = {};
          (d.hits && d.hits.hits ? d.hits.hits : []).forEach(function (h) {
            var m = h.metadata || {};
            if (typeof m.citation_count !== "number") return;
            (m.dois || []).forEach(function (x) {
              by[String(x.value).toLowerCase()] = m.citation_count;
            });
            (m.arxiv_eprints || []).forEach(function (x) {
              by[String(x.value).toLowerCase()] = m.citation_count;
            });
          });
          b.forEach(function (x) {
            if (typeof by[x.key] === "number") {
              x.row.citations = by[x.key];
              x.row.citeFrom = CITE_SOURCE;
              citeCache[x.key] = by[x.key];
            } else {
              citeCache[x.key] = false;
            }
          });
        }, function () {
          // A failed lookup leaves those rows without a count, which is the
          // same state they were in a moment ago. It must never take the
          // search down with it.
        });
    }));
  }

  /* ---------------------------------------------------------------
     Subfield classification

     Which corner of physics a paper belongs to. The scheme is not invented
     here: it is the arXiv subject taxonomy (arxiv.org/category_taxonomy) —
     the classification the papers were actually deposited under — collapsed
     into the handful of groups a reader of this page separates by eye. Each
     database is asked for whatever part of it it holds:

       INSPIRE           arxiv_eprints[].categories, plus its own
                         inspire_categories (Phenomenology-HEP,
                         Experiment-HEP, Astrophysics, Gravitation and
                         Cosmology, Theory-Nucl, Instrumentation, …), which
                         is the only classification a record with no eprint
                         carries
       arXiv / DataCite  subjects deposited under subjectScheme "arXiv"
       OpenAlex          primary_topic, from its domain/field/subfield/topic
                         hierarchy
       Semantic Scholar  s2FieldsOfStudy
       Crossref          subject, when the publisher deposited any

     NEUTRINO PHYSICS IS NOT AN ARXIV CATEGORY. It runs through hep-ph,
     hep-ex, astro-ph.HE and nucl-ex at once — which is precisely why a page
     on this site needs it as a group of its own. So it is decided separately
     — from OpenAlex's topic, or from the words of the title and of the venue,
     the venue being how a proceedings volume of a neutrino conference gives
     its own subject away — and it OUTRANKS the arXiv bucket: a hep-ph paper
     on oscillations belongs under neutrinos, not under phenomenology.

     The label is a reading aid over the results of one search. It is not a
     claim about the paper beyond what the databases themselves say, and a
     record none of them classified is shown as Unclassified rather than
     guessed into a group.
     --------------------------------------------------------------- */

  var SUBFIELDS = [
    { id: "neutrino", label: "Neutrino physics" },
    { id: "hep-ph",   label: "Particle phenomenology" },
    { id: "hep-ex",   label: "Particle experiment" },
    { id: "hep-th",   label: "Fields, strings & math. physics" },
    { id: "nucl",     label: "Nuclear physics" },
    { id: "astro-he", label: "Astroparticle & HE astrophysics" },
    { id: "cosmo",    label: "Cosmology & gravitation" },
    { id: "astro",    label: "Astronomy & astrophysics" },
    { id: "instr",    label: "Instrumentation & data" },
    { id: "other",    label: "Other physics" },
    { id: "none",     label: "Unclassified" }
  ];

  var SUBFIELD_LABEL = {};
  var SUBFIELD_ORDER = {};
  SUBFIELDS.forEach(function (s, i) {
    SUBFIELD_LABEL[s.id] = s.label;
    SUBFIELD_ORDER[s.id] = i;
  });

  // arXiv category -> group, keys lower case. A category with a subdivision
  // ("astro-ph.co") is looked up whole and then by its archive alone, so a
  // subdivision arXiv adds after this was written lands in its archive's
  // group instead of falling through to "other".
  var ARXIV_GROUP = {
    "hep-ph": "hep-ph",
    "hep-ex": "hep-ex",
    "hep-th": "hep-th", "hep-lat": "hep-th", "math-ph": "hep-th",
    "nucl-th": "nucl", "nucl-ex": "nucl",
    "astro-ph.he": "astro-he",
    "astro-ph.co": "cosmo", "gr-qc": "cosmo",
    "astro-ph": "astro", "astro-ph.ga": "astro",
    "astro-ph.sr": "astro", "astro-ph.ep": "astro",
    "astro-ph.im": "instr", "physics.ins-det": "instr",
    "physics.acc-ph": "instr", "physics.data-an": "instr",
    "physics.comp-ph": "instr"
  };

  // INSPIRE's own subject terms, lower-cased. Verified against the live API
  // rather than recalled: a record's inspire_categories[].term.
  var INSPIRE_GROUP = {
    "phenomenology-hep": "hep-ph",
    "experiment-hep": "hep-ex",
    "theory-hep": "hep-th",
    "lattice": "hep-th",
    "math and math physics": "hep-th",
    "theory-nucl": "nucl",
    "experiment-nucl": "nucl",
    "astrophysics": "astro-he",
    "gravitation and cosmology": "cosmo",
    "instrumentation": "instr",
    "accelerators": "instr",
    "computing": "instr",
    "general physics": "other",
    "other": "other"
  };

  // Word boundaries, not substrings: "neutron" is not "neutrino", and a
  // title that merely contains the letters is not a neutrino paper. The
  // spellings are those that actually appear in titles in this field.
  var NU_RE = new RegExp(
    "\\b(?:neutrino|neutrinos|neutrino's|antineutrino|antineutrinos|" +
    "neutrinoless|cevns|pmns|majoron|majorons)\\b" +
    "|\\bdouble[\\s-]beta\\b|0\\u03bd\\u03b2\\u03b2|\\b0nubb\\b", "i");

  // Last resort, on OpenAlex's topic wording and Semantic Scholar's fields.
  // Ordered: the first pattern that matches wins, so the narrower subjects
  // are listed before the ones whose words they contain.
  var TOPIC_GROUP = [
    [/dark matter|cosmic ray|astroparticle|gamma-ray|high[\s-]energy astro/i, "astro-he"],
    [/cosmolog|dark energy|inflation|cosmic microwave|gravitation|relativit/i, "cosmo"],
    [/astronom|galax|stellar|solar physic|planet/i, "astro"],
    [/nuclear/i, "nucl"],
    [/string theory|quantum field|supersymmetr|conformal|lattice|mathematical physic/i, "hep-th"],
    [/particle|collider|chromodynamic|hadron|standard model|quark/i, "hep-ph"],
    [/detector|instrument|accelerator|data analysis/i, "instr"],
    [/physics/i, "other"]
  ];

  function entityInTitle(r) {
    var title = String(r.title || "");
    var more = [r.abstract, (r.keywords || []).join(" "), (r.collabs || []).join(" ")].join(" ");
    for (var name in ENTITIES) {
      if (!Object.prototype.hasOwnProperty.call(ENTITIES, name)) continue;
      var rx = new RegExp("\\b" + name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i");
      if (!rx.test(title)) continue;
      if (rx.test((r.collabs || []).join(" "))) return name;
      var ctx = ENTITIES[name].ctx || [];
      for (var i = 0; i < ctx.length; i++) {
        if (new RegExp("\\b" + ctx[i] + "\\b", "i").test(more)) return name;
      }
    }
    return "";
  }

  function subfieldOf(r) {
    var i;
    if (NU_RE.test(String(r.title || "") + " " + String(r.journal || ""))) {
      return "neutrino";
    }
    if (/neutrino/i.test(r.topic || "")) return "neutrino";
    /* A neutrino experiment named in the title ("Sensitivity of JUNO to …")
       counts when the record confirms it is that experiment: the signing
       collaboration, or one of the entity's context words in the abstract
       or keywords. A mere mention of neutrinos in an abstract does not — a
       dark-matter paper can mention the neutrino floor. */
    var expHit = entityInTitle(r);
    if (expHit) return "neutrino";

    var cats = (r.cats || []).map(function (c) { return String(c).toLowerCase(); });
    for (i = 0; i < cats.length; i++) {
      var g = ARXIV_GROUP[cats[i]] || ARXIV_GROUP[cats[i].split(".")[0]];
      if (!g && /^(?:physics|quant-ph|cond-mat|nlin|math)/.test(cats[i])) g = "other";
      if (g) return g;
    }

    var ins = (r.inspireCats || []).map(function (c) { return String(c).toLowerCase(); });
    for (i = 0; i < ins.length; i++) {
      if (INSPIRE_GROUP[ins[i]]) return INSPIRE_GROUP[ins[i]];
    }

    var words = [r.topic, r.topicField].concat(r.s2fields || [], r.crSubjects || [])
                  .filter(Boolean).join(" ");
    for (i = 0; i < TOPIC_GROUP.length; i++) {
      if (TOPIC_GROUP[i][0].test(words)) return TOPIC_GROUP[i][1];
    }
    return "none";
  }

  /* ---------------------------------------------------------------
     Relevance

     Each database ranks in its own way, over its own subset. Once the
     answers are merged those rankings cannot be compared — the third hit at
     OpenAlex and the third at INSPIRE are not equally good — so an order
     that means the same thing for every row has to be computed here, from
     the query and the record alone. Deliberately simple and bounded, and
     every term is something visible in the row itself:

       up to 45   the authors asked for, by the fraction actually present
       up to 40   the title asked for: 40 when it matches, 25 when contained
       up to 25   the topic words, by the fraction found in title or venue
                  (a word found only in the journal name counts two fifths)
              8   a collaboration name matched
       up to 12   corroboration: 4 for each database that returned the record
       up to  6   PRECISE mode only: the topic words found in the abstract or
                  the subject keywords but NOT in the title, by their fraction.
                  Deliberately below the title's 25: a paper that says it in
                  the title answers the query better than one that merely
                  mentions it, and the whole abstract bonus is worth less than
                  a quarter of what the title match is. It exists to order
                  records that all passed the strong-match gate, not to
                  rescue any.

     TWO NUMBERS, NOT ONE. Citations and age are returned separately and are
     consulted ONLY when the match score is exactly equal — a genuine
     tie-break, not a term. They were a term once, worth up to 10 and 2
     points, and that quietly made this page do the thing the rest of the
     file exists to avoid: a paper with 20 000 citations matching four query
     words out-ranked one with none matching all five. The page says
     citations only break ties, and this is what makes that sentence true.
     Sorting BY citations is a button of its own, where it is the question.
     --------------------------------------------------------------- */

  function relevance(r, f, terms) {
    var s = 0;
    if (f.author.length) {
      var have = r.authors.map(surnameOf);
      var hit = 0;
      f.author.forEach(function (want) {
        var w = surnameOf(want);
        if (have.some(function (h) { return h === w || h.indexOf(w) === 0; })) hit++;
      });
      s += 45 * (hit / f.author.length);
    }
    if (f.title) {
      var a = normTitle(r.title), b = normTitle(f.title);
      if (a === b) s += 40;
      else if (b.length > 12 && a.indexOf(b) > -1) s += 25;
    }
    if (terms.length) {
      var inTitle = " " + normTitle(r.title) + " ";
      var inVenue = " " + normTitle(r.journal || "") + " ";
      var n = 0;
      terms.forEach(function (t) {
        if (inTitle.indexOf(t) > -1) n += 1;
        else if (inVenue.indexOf(t) > -1) n += 0.4;
      });
      s += 25 * Math.min(1, n / terms.length);
    }
    if (terms.length && mode === "precise") {
      var tl = " " + normTitle(r.title) + " ";
      var body = " " + normTitle((r.abstract || "") + " " +
                                 (r.keywords || []).join(" ")) + " ";
      var m = 0;
      terms.forEach(function (t) {
        if (!hasTerm(tl, t) && hasTerm(body, t)) m += 1;
      });
      s += 6 * (m / terms.length);
    }
    if (f.collab) {
      var hay = normTitle(r.title + " " + (r.journal || "") + " " +
                          (r.collabs || []).join(" "));
      if (hay.indexOf(normTitle(f.collab)) > -1) s += 8;
    }
    s += Math.min(12, 4 * (r.sources || [r.source]).length);
    return s;
  }

  /* The tie-break, on the same bounded scale, consulted only when two rows
     score exactly the same match. Ten points of citations against two of
     recency: between two papers the query cannot tell apart, the one the
     field has actually used comes first. */
  function tieBreak(r) {
    var t = 0;
    if (typeof r.citations === "number" && r.citations > 0) {
      t += Math.min(10, 4 * Math.log(1 + r.citations) / Math.LN10);
    }
    var y = parseInt(String(r.date || r.year || "").slice(0, 4), 10);
    if (y && y >= THIS_YEAR - 3) t += 2;
    return t;
  }

  /* ---------------------------------------------------------------
     Ordering

     Four keys, each reversible. The ordering is applied HERE, to the merged
     set already on the page, and changing it never refetches: the answer is
     already downloaded, and a click that costs five API calls to reorder
     twenty rows the reader is looking at would be a worse page.

     Which also fixes what "most cited" can honestly mean. Asking INSPIRE for
     sort=mostcited does not return the most cited papers ON the subject, it
     returns the most cited papers that MENTION the words — the failure this
     file already records for topic searches (see fromInspire). The databases
     are therefore always asked for their own best matches; the citation
     ranking is over that set, and the status line says how large it is.

     A record missing the key sinks to the bottom in BOTH directions. It is
     not "the smallest year", and floating undated records to the top of an
     ascending sort would be a bug dressed as an order.
     --------------------------------------------------------------- */

  // One key for time, not two. There were a "Year" and a "Month" button, and
  // the pair was a distinction without a use: the same question asked at two
  // resolutions, where the finer one answers the coarser as well. A record
  // known only to the year sorts at its January, so nothing is lost.
  var SORTS = [
    { id: "relevance", label: "Relevance",
      down: "best match first", up: "weakest match first" },
    { id: "date", label: "Date",
      down: "newest first", up: "oldest first" },
    { id: "citations", label: "Citations",
      down: "most cited first", up: "least cited first" },
    { id: "subfield", label: "Subfield",
      down: "largest group first", up: "smallest group first" }
  ];

  var sortKey = "relevance";
  var sortDir = -1;                 // -1 descending, +1 ascending
  var hidden = {};                  // subfield id -> true when filtered out

  // "2025-03-10" and a bare "2025" both order; a year alone is placed at its
  // January, which is where a record that only says "2025" belongs — that is
  // also what lets ONE key do the work: a record known only to the year still
  // sorts against records known to the day, instead of needing a coarser
  // button of its own.
  function dateKey(r) {
    var d = r.date || (r.year ? String(r.year) + "-01-01" : "");
    if (!/^\d{4}/.test(d)) return null;
    return (d + "-01-01").slice(0, 10);
  }

  function citeKey(r) {
    return typeof r.citations === "number" ? r.citations : null;
  }

  // Best match first, then the tie-break. The direction is NOT applied here:
  // this is what "equal for the chosen key" falls back to, and a reader
  // sorting by year ascending still wants the better match first among the
  // papers of one year.
  function byMatch(a, b) {
    return (b.score - a.score) || (b.tie - a.tie);
  }

  function compareBy(key, dir) {
    return function (a, b) {
      var ka, kb;
      if (key === "date") { ka = dateKey(a); kb = dateKey(b); }
      else if (key === "citations") { ka = citeKey(a); kb = citeKey(b); }
      else {
        // Relevance: the match decides, the tie-break settles what it
        // cannot, and BOTH follow the chosen direction.
        return dir * ((a.score - b.score) || (a.tie - b.tie));
      }
      if (ka === null && kb === null) return byMatch(a, b);
      if (ka === null) return 1;            // always last, both directions
      if (kb === null) return -1;
      if (ka === kb) return byMatch(a, b);
      // A date key is an ISO string, a citation count is a number; `<`
      // orders both correctly.
      return dir * (ka < kb ? -1 : 1);
    };
  }

  /* ---------------------------------------------------------------
     Rendering
     --------------------------------------------------------------- */

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  // "2025-03-10" -> "Mar 2025";  "2025" -> "2025"
  function prettyDate(s) {
    var m = /^(\d{4})(?:-(\d{2}))?/.exec(s);
    if (!m) return s;
    return m[2] ? MON[parseInt(m[2], 10) - 1] + " " + m[1] : m[1];
  }

  var SRC_CLASS = {
    "INSPIRE-HEP": "src--inspire",
    "Crossref": "src--crossref",
    "OpenAlex": "src--openalex",
    "Semantic Scholar": "src--s2"
  };

  /* Eleven subfields cannot each have a legible colour of their own, and a
     palette that large stops being a code and becomes decoration. So the chip
     carries the precise label as TEXT and is tinted by the broad family it
     belongs to — five tones, every one of them an accent token already
     measured against this section's background in tools/tests/test_theme.js. */
  var SUBFIELD_TONE = {
    "neutrino": "nu",
    "hep-ph": "hep", "hep-ex": "hep",
    "hep-th": "thy", "nucl": "thy",
    "astro-he": "sky", "cosmo": "sky", "astro": "sky",
    "instr": "dim", "other": "dim", "none": "dim"
  };

  var BUCKET_LABEL = {};
  BUCKETS.forEach(function (b) { BUCKET_LABEL[b.id] = b.label; });

  // `showMatch` only outside the relevance view. There the rows already sit
  // under the heading that names their match quality, and repeating it on
  // every row would be noise; in a flat or subfield-grouped list that heading
  // is gone and the information would be lost with it.
  function renderItem(r, showMatch) {
    var authors = r.authors.filter(Boolean).join(", ") + (r.more ? ", et al." : "");
    var when = r.date || (r.year ? String(r.year) : "");
    var sf = r.subfield || "none";
    // The subfield chip leads the metadata line, at the OPPOSITE END of the
    // row from the source badges. It used to sit beside them, and on a site
    // whose subfield tones and source tones are drawn from one palette that
    // put two same-coloured pills side by side — "Particle phenomenology"
    // next to "INSPIRE-HEP" in the same blue. Separating them is also the
    // truer grouping: the subfield is a fact about the PAPER, the badges are
    // about where we found it.
    var meta = compact([
      '<span class="sf sf--' + SUBFIELD_TONE[sf] + '">' +
        esc(SUBFIELD_LABEL[sf]) + "</span>",
      when && '<time class="pub__year" datetime="' + esc(when) + '">' +
              esc(prettyDate(when)) + "</time>",
      r.journal && '<span class="journal">' + esc(r.journal) + "</span>",
      typeof r.citations === "number" &&
        '<span class="muted" title="Citation count from INSPIRE-HEP">' +
          r.citations + " citations</span>"
    ]).join("");
    var links = r.links.map(function (l) {
      return '<a href="' + esc(l.href) + '" target="_blank" rel="noopener noreferrer">' +
             esc(l.label) + "</a>";
    }).join("");
    var srcs = (r.sources || [r.source]).map(function (s) {
      return '<span class="src ' + (SRC_CLASS[s] || "") + '">' + esc(s) + "</span>";
    }).join("");
    // Only the match chip stays with the badges: it says why the record came
    // back, which is of a piece with which database sent it.
    var tags = (showMatch && BUCKET_LABEL[r.bucket])
      ? '<span class="sf sf--match">' + esc(BUCKET_LABEL[r.bucket]) + "</span>"
      : "";
    var first = r.links[0];
    var title = first
      ? '<a class="pub__title" href="' + esc(first.href) +
        '" target="_blank" rel="noopener noreferrer">' + esc(r.title) + "</a>"
      : '<span class="pub__title">' + esc(r.title) + "</span>";
    return "<li>" + title +
           '<div class="pub__authors">' + esc(authors) + "</div>" +
           '<div class="pub__ref">' + meta + links + '<span class="src-row">' +
           tags + srcs + "</span></div></li>";
  }

  // A failed database is not reported here: it gets a badge of its own above
  // the results (renderBadges), so that it never takes the place of them.
  function head(rows) {
    var out = [];
    if (!rows.length && !state.pending.length) {
      out.push('<p class="muted">' + (anyHidden()
        ? "Every result is in a subfield you have switched off."
        : "No results. Try loosening the query or widening the dates.") +
        "</p>");
    }
    return out;
  }

  // Relevance view: the match buckets, strongest first — the grouping IS the
  // relevance statement, and the score decides the order inside each group.
  //
  // THE SEQUENCE OF BUCKETS REVERSES TOO. It did not, once: ascending
  // relevance reordered the rows inside each group while leaving the groups
  // themselves strongest-first, so the best match on the page stayed in
  // position one — while the status line and the button's accessible name
  // both announced "weakest match first". A control that says it reversed
  // and did not is worse than no control.
  function renderBuckets(rows) {
    var out = head(rows);
    if (!rows.length) return out.join("");
    var cmp = compareBy("relevance", sortDir);
    var order = sortDir < 0 ? BUCKETS : BUCKETS.slice().reverse();
    order.forEach(function (b) {
      var group = rows.filter(function (r) { return r.bucket === b.id; })
                      .sort(cmp);
      if (!group.length) return;
      out.push(
        '<section class="lit-bucket lit-bucket--' + b.id + '">' +
        '<h3 class="lit-group">' + esc(b.label) +
        '<span class="count">' + group.length + "</span></h3>" +
        '<p class="lit-group__note">' + esc(b.note) + "</p>" +
        '<ul class="publist">' + group.map(function (r) {
          return renderItem(r, false);
        }).join("") + "</ul></section>");
    });
    return out.join("");
  }

  // Year, month and citations: one list. Buckets would cut the very ordering
  // that was asked for into four unrelated runs — a 2027 paper below a 1998
  // one because they matched differently.
  function renderFlat(rows) {
    var out = head(rows);
    if (!rows.length) return out.join("");
    var sorted = rows.slice().sort(compareBy(sortKey, sortDir));
    out.push('<ul class="publist">' + sorted.map(function (r) {
      return renderItem(r, true);
    }).join("") + "</ul>");
    return out.join("");
  }

  // Subfield view: one section per group. The groups are ordered by size,
  // reversibly; inside a group the order is relevance, because "the neutrino
  // papers" is a question about which of them, not about which order.
  function renderSubfields(rows) {
    var out = head(rows);
    if (!rows.length) return out.join("");
    var by = {};
    rows.forEach(function (r) { (by[r.subfield] = by[r.subfield] || []).push(r); });
    var ids = Object.keys(by).sort(function (a, b) {
      if (by[a].length !== by[b].length) {
        return sortDir * (by[a].length - by[b].length);
      }
      return SUBFIELD_ORDER[a] - SUBFIELD_ORDER[b];
    });
    var cmp = compareBy("relevance", -1);
    ids.forEach(function (id) {
      var group = by[id].sort(cmp);
      out.push(
        '<section class="lit-bucket lit-bucket--sf sf-block--' +
        SUBFIELD_TONE[id] + '">' +
        '<h3 class="lit-group">' + esc(SUBFIELD_LABEL[id]) +
        '<span class="count">' + group.length + "</span></h3>" +
        '<ul class="publist">' + group.map(function (r) {
          return renderItem(r, true);
        }).join("") + "</ul></section>");
    });
    return out.join("");
  }

  function renderOutbound(f, parsed) {
    var links = [
      ["arXiv", arxivUrl(f), "btn--cyan"],
      ["NASA ADS", adsUrl(f), "btn--ghost"],
      ["Google Scholar", scholarUrl(f), "btn--ghost"],
      ["INSPIRE (site)",
       "https://inspirehep.net/search?q=" + encodeURIComponent(inspireQuery(f)),
       "btn--ghost"]
    ];
    if (parsed && parsed.arxivId) {
      links.unshift(["Open arXiv:" + parsed.arxivId,
                     "https://arxiv.org/abs/" + parsed.arxivId, ""]);
    }
    elOutbound.innerHTML = links.map(function (l) {
      return '<a class="btn btn--sm ' + l[2] + '" href="' + esc(l[1]) +
             '" target="_blank" rel="noopener noreferrer">' + esc(l[0]) + " ↗</a>";
    }).join("");
  }

  /* ---------------------------------------------------------------
     The controls over the results, and redrawing without refetching

     Everything below works on `state`, the merged answer of the last search.
     A click on a sort button or a subfield filter redraws from it; no request
     leaves the browser. That is what makes the buttons instant, and it is
     also the honest scope of the ordering: it ranks what was retrieved, and
     the status line says how much that is.
     --------------------------------------------------------------- */

  var EMPTY_STATE = { rows: [], failures: [], pending: [], dbs: 0, merged: 0, gated: 0, discOut: 0, loosened: "" };
  var state = JSON.parse(JSON.stringify(EMPTY_STATE));

  function anyHidden() {
    return Object.keys(hidden).some(function (k) { return hidden[k]; });
  }

  function visibleRows() {
    return state.rows.filter(function (r) { return !hidden[r.subfield]; });
  }

  /* The sort bar is drawn from the start, before any search has run, and the
     filter bar only once there is something to filter.

     Not symmetry for its own sake: the order is pushed UPSTREAM for the date
     keys — a search with Year or Month active asks each database for its most
     recent records, which changes which twenty come back. Hidden until the
     first answer arrived, the bar made that unreachable on the query that
     needed it, and a reader wanting the twenty most recent papers had to
     search, click, and search again. The filter bar has no such duty: it can
     only narrow an answer that exists. */
  function renderControls() {
    if (!elSortBar || !elFilters) return;
    var live = !!state.rows.length;

    var bits = ['<span class="lit-sort__label">Sort by</span>'];
    SORTS.forEach(function (o) {
      var on = o.id === sortKey;
      var way = on ? (sortDir < 0 ? o.down : o.up) : o.down;
      // The arrow is decorative; the direction is in the accessible name, so
      // a screen reader announces "Year, newest year first" and not "Year".
      bits.push('<button type="button" class="lit-sort__btn" data-sort="' +
        o.id + '" aria-pressed="' + (on ? "true" : "false") +
        '" aria-label="' + esc(o.label + ", " + way +
        (on ? " (press again to reverse)" : "")) + '" title="' + esc(way) + '">' +
        esc(o.label) + '<span class="lit-sort__dir" aria-hidden="true">' +
        (on ? (sortDir < 0 ? "\u2193" : "\u2191") : "") + "</span></button>");
    });
    elSortBar.innerHTML = bits.join("");
    elSortBar.hidden = false;

    if (!live) { elFilters.hidden = true; elFilters.innerHTML = ""; return; }

    // Counts are over ALL rows, not over the visible ones: a filter chip
    // whose number changed as you switched other chips off would be telling
    // you about the filter rather than about the answer.
    var counts = {};
    state.rows.forEach(function (r) {
      counts[r.subfield] = (counts[r.subfield] || 0) + 1;
    });
    var ids = Object.keys(counts).sort(function (a, b) {
      return SUBFIELD_ORDER[a] - SUBFIELD_ORDER[b];
    });
    if (ids.length < 2) { elFilters.hidden = true; elFilters.innerHTML = ""; return; }

    var f = ['<span class="lit-sort__label">Subfield</span>'];
    ids.forEach(function (id) {
      var off = !!hidden[id];
      f.push('<button type="button" class="lit-filter sf--' + SUBFIELD_TONE[id] +
        '" data-sf="' + id + '" aria-pressed="' + (off ? "false" : "true") +
        '" aria-label="' + esc(SUBFIELD_LABEL[id] + ", " + counts[id] +
        (off ? " papers, hidden — show them" : " papers, shown — hide them")) +
        '">' + esc(SUBFIELD_LABEL[id]) +
        '<span class="lit-filter__n">' + counts[id] + "</span></button>");
    });
    // No aria-pressed on this one, deliberately: it is a command, not a
    // toggle, and marking it pressed/unpressed would describe a state it does
    // not have. The label says what it does instead.
    if (anyHidden()) {
      f.push('<button type="button" class="lit-filter lit-filter--all" ' +
             'data-sf="*" aria-label="Show every subfield again">' +
             "Show all</button>");
    }
    elFilters.innerHTML = f.join("");
    elFilters.hidden = false;
  }

  function renderStatus(shown) {
    if (!state.rows.length) {
      if (state.pending.length) {
        elStatus.innerHTML = '<span class="spin" aria-hidden="true"></span> ' +
                             "Querying the databases …";
      } else {
        elStatus.textContent = state.dbs === 0
          ? "No database could be reached."
          : "No results. Try loosening the query or widening the dates.";
      }
      return;
    }
    var active = SORTS.filter(function (o) { return o.id === sortKey; })[0];
    var bits = [];
    bits.push(state.rows.length + " paper" + (state.rows.length === 1 ? "" : "s") +
              " from " + state.dbs + " database" + (state.dbs === 1 ? "" : "s"));
    if (state.merged > 0) {
      bits.push(state.merged === 1 ? "1 duplicate record merged"
                                   : state.merged + " duplicate records merged");
    }
    if (state.gated > 0) {
      bits.push(state.gated === 1 ? "1 off-topic record dropped"
                                  : state.gated + " off-topic records dropped");
    }
    if (state.discOut > 0) {
      bits.push(state.discOut + " outside neutrino physics hidden");
    }
    if (state.pending.length) {
      bits.push("still waiting for " + state.pending.join(", "));
    }
    // Said plainly, because it changes what the answer means: these are not
    // the papers the question asked for, they are the papers of the nearest
    // question INSPIRE could answer.
    if (state.loosened) {
      bits.push("INSPIRE answered only without " + state.loosened);
    }
    if (shown.length !== state.rows.length) {
      bits.push(shown.length + " shown");
    }
    bits.push("ordered by " + active.label.toLowerCase() + ", " +
              (sortDir < 0 ? active.down : active.up));
    elStatus.textContent = bits.join(" · ") + ". Links open in a new tab.";
  }

  /* Both bars are redrawn wholesale on every click, which throws away the
     focused element — so a reader working by keyboard would press Enter on
     "Year" and find the focus back at the top of the document, with no way to
     reverse it without tabbing the whole way down again. Put it back on the
     button that was just used. */
  function refocus(bar, sel) {
    var el = bar && bar.querySelector(sel);
    if (el && document.activeElement !== el) el.focus();
  }

  /* One row of compact badges above the results. A database that is still
     answering shows "NAME …"; one that failed says so, with the technical
     reason in the tooltip. Neither is ever a message in place of results: the
     other databases' records are on the page whatever happens to this one. */
  function renderBadges() {
    if (!elBadges) return;
    var out = [];
    state.pending.forEach(function (n) {
      out.push('<span class="lit-badge lit-badge--pending">' + esc(n) + " …</span>");
    });
    state.failures.forEach(function (x) {
      var why = (x.err && x.err.message) || String(x.err || "error");
      out.push('<span class="lit-badge lit-badge--fail" role="status" title="' +
               esc(why) + '">' + esc(x.name) + " temporarily unavailable</span>");
    });
    elBadges.innerHTML = out.join("");
    elBadges.hidden = !out.length;
  }

  function draw() {
    // Redrawn as each database settles, so a reader mid-keystroke on a sort
    // or filter button must not lose the focus to the rebuild.
    var ae = document.activeElement;
    var keep = ae && ae.getAttribute && (
      (ae.getAttribute("data-sort") && [elSortBar, '[data-sort="' + ae.getAttribute("data-sort") + '"]']) ||
      (ae.getAttribute("data-sf") && [elFilters, '[data-sf="' + ae.getAttribute("data-sf") + '"]']));
    renderBadges();
    renderControls();
    var rows = visibleRows();
    elResults.innerHTML =
      sortKey === "relevance" ? renderBuckets(rows)
      : sortKey === "subfield" ? renderSubfields(rows)
      : renderFlat(rows);
    renderStatus(rows);
    if (keep && keep[0]) refocus(keep[0], keep[1]);
  }

  if (elSortBar) {
    elSortBar.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("[data-sort]") : null;
      if (!b) return;
      var id = b.getAttribute("data-sort");
      // Clicking the active key reverses it; clicking another key starts it
      // in its natural direction, which for every key here is descending —
      // newest, most cited, best match, largest group.
      if (id === sortKey) sortDir = -sortDir;
      else { sortKey = id; sortDir = -1; }
      draw();
      refocus(elSortBar, '[data-sort="' + id + '"]');
    });
  }

  if (elFilters) {
    elFilters.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("[data-sf]") : null;
      if (!b) return;
      var id = b.getAttribute("data-sf");
      if (id === "*") hidden = {};
      else hidden[id] = !hidden[id];
      draw();
      // "Show all" disappears the moment it works, so the focus goes to the
      // chip the reader was last thinking about instead — never to nowhere.
      refocus(elFilters, id === "*" ? "[data-sf]" : '[data-sf="' + id + '"]');
    });
  }

  /* ---------------------------------------------------------------
     Wiring
     --------------------------------------------------------------- */

  function setMode(m) {
    mode = m;
    if (!elMode) return;
    Array.prototype.forEach.call(elMode.querySelectorAll("[data-mode]"), function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-mode") === m ? "true" : "false");
    });
  }

  if (elMode) {
    elMode.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("[data-mode]") : null;
      if (!b) return;
      setMode(b.getAttribute("data-mode"));
      refresh();
    });
  }
  if (elDisc) elDisc.addEventListener("change", refresh);

  /* One search is a set of `sources` that settle at different times. The page
     keeps what has settled so far in `results` and, each time one more
     arrives, builds the whole answer again from ALL of it (`assemble`):
     merge, gate, classify, score. The merge is therefore re-run, not
     extended, which is why it works on copies and why the same rows can be
     assembled any number of times. Changing the mode or the discipline does
     the same without asking the databases anything. */
  var current = null;       // the search in progress or last finished

  function assemble(c) {
    var groups = c.names.map(function (n) { return c.results[n]; })
                        .filter(Boolean);
    var ok = groups.filter(function (g) { return !g.err; });
    ok.forEach(function (g) { g.rows.forEach(saneDates); });
    var rows = mergeAll(ok);
    var afterMerge = rows.length;
    var f = c.f;

    var terms = gateTerms(f);
    if (mode === "precise") {
      var ents = queryEntities(f);
      rows = rows.filter(function (r) { return strongMatch(r, f, terms, ents); });
    } else {
      rows = rows.filter(function (r) {
        var physicsNative = (r.sources || [r.source]).some(function (s) {
          return PHYSICS_NATIVE[s];
        });
        return physicsNative || passesTermGate(r, terms);
      });
    }
    var gated = afterMerge - rows.length;

    // The discipline is a post-filter on the same classification the
    // subfield chips use; "all physics" leaves everything in.
    rows.forEach(function (r) { r.subfield = subfieldOf(r); });
    var before = rows.length;
    if (elDisc && elDisc.value === "neutrino") {
      rows = rows.filter(function (r) { return r.subfield === "neutrino"; });
    }

    citesFromCache(rows);
    annotate(rows, f, terms);

    var found = ok.reduce(function (n, g) { return n + g.rows.length; }, 0);
    state = {
      rows: rows,
      failures: groups.filter(function (g) { return g.err; })
                      .map(function (g) { return { name: g.name, err: g.err }; }),
      pending: c.names.filter(function (n) { return !c.results[n]; }),
      dbs: ok.length,
      merged: found - afterMerge,
      gated: gated,
      discOut: before - rows.length,
      loosened: inspireLoosened
    };
  }

  // Classified and scored here, not at every click: the sort buttons reorder
  // the same objects afterwards, and recomputing a score on every click would
  // be work for nothing and a chance for the order to disagree with the
  // labels the reader is looking at. The tie-break reads the citation counts,
  // so this runs again once the INSPIRE lookup has filled them in.
  function annotate(rows, f, terms) {
    rows.forEach(function (r) {
      r.bucket = classify(r, f);
      r.subfield = subfieldOf(r);
      r.score = relevance(r, f, terms);
      r.tie = tieBreak(r);
    });
  }

  // Redraw the current search with the current mode and discipline.
  function refresh() {
    if (!current) return;
    var c = current;
    assemble(c);
    draw();
    if (c.names.some(function (n) { return !c.results[n]; })) return;
    finish(c);
  }

  // Everything has settled: INSPIRE is asked, once, for the citation counts
  // of the records it did not itself return, and the page is drawn a last time.
  function finish(c) {
    var rows = state.rows;
    fillCitations(rows, c.useInspire).then(function () {
      if (current !== c || state.rows !== rows) return;
      annotate(rows, c.f, gateTerms(c.f));
      draw();
    });
  }

  function run(ev) {
    if (ev) ev.preventDefault();
    var parsed = applyParse();
    var f = fields();

    // An identifier counts as something to search for. It used to not, so a
    // pasted arXiv id or DOI stopped the page before a single request left.
    if (!f.author.length && !f.title && !f.topic && !f.collab &&
        !f.arxivId && !f.doi) {
      elStatus.textContent = "Type something to search — an author, a title, a topic, a year.";
      elResults.innerHTML = "";
      elOutbound.innerHTML = "";
      return;
    }

    renderOutbound(f, parsed);
    elStatus.innerHTML = '<span class="spin" aria-hidden="true"></span> Querying the databases …';
    elResults.innerHTML = "";
    // A subfield filter belongs to one answer: keeping "neutrino physics
    // only" switched on across a search for something else would hide the new
    // answer behind a decision taken about the old one. The sort key is the
    // opposite case — it is a standing preference and survives.
    hidden = {};
    inspireLoosened = "";
    citeCache = {};
    current = null;
    state = JSON.parse(JSON.stringify(EMPTY_STATE));
    renderBadges();
    renderControls();

    // Bring the results area into view and give it focus, so the answer is
    // where the eye already is — and so keyboard and screen-reader users land
    // on it too rather than being left at the top of the form.
    var pane = document.getElementById("lit-pane") || elStatus;
    pane.scrollIntoView({
      behavior: reducedMotion() ? "auto" : "smooth",
      block: "start"
    });
    elStatus.setAttribute("tabindex", "-1");
    elStatus.focus({ preventScroll: true });

    var wanted = [];
    // Also decides whether the citation lookup may run at all: with INSPIRE
    // unticked the reader has asked not to use the one source this page
    // trusts for counts, so no count is shown.
    var useInspire = $("#src-inspire").checked;
    if (useInspire) wanted.push(["INSPIRE-HEP", fromInspire]);
    if ($("#src-crossref").checked) wanted.push(["Crossref", fromCrossref]);
    if ($("#src-openalex").checked) wanted.push(["OpenAlex", fromOpenAlex]);
    if ($("#src-arxiv") && $("#src-arxiv").checked) wanted.push(["arXiv", fromArxiv]);
    if ($("#src-s2") && $("#src-s2").checked) wanted.push(["Semantic Scholar", fromS2]);

    if (!wanted.length) {
      elStatus.textContent = "Select at least one database.";
      return;
    }

    var c = current = {
      f: f, useInspire: useInspire, results: {},
      names: wanted.map(function (w) { return w[0]; })
    };
    refresh();            // nothing has settled yet: the pending badges appear

    wanted.forEach(function (w) {
      var p;
      // A builder that throws is a failed source like any other.
      try { p = w[1](f); } catch (e) { p = Promise.reject(e); }
      p.then(
        function (rows) { return { name: w[0], rows: rows || [] }; },
        function (err) { return { name: w[0], rows: [], err: err || new Error("error") }; }
      ).then(function (g) {
        if (current !== c) return;       // a newer search has replaced this one
        c.results[w[0]] = g;
        refresh();
      });
    });
  }

  form.addEventListener("submit", run);

  $("#lit-clear").addEventListener("click", function () {
    form.reset();
    userTouched = {};
    hidden = {};
    inspireLoosened = "";
    current = null;
    setMode("precise");
    state = JSON.parse(JSON.stringify(EMPTY_STATE));
    renderBadges();
    renderControls();
    elResults.innerHTML = "";
    elOutbound.innerHTML = "";
    elStatus.textContent = "";
    renderChips(null);
    elFree.focus();
  });

  // Example queries: a different handful on every visit, drawn from this
  // list, so no single query (or author) is the page's standing suggestion.
  // [query sent, text shown]
  var EXAMPLES = [
    ["JUNO reactor oscillation 2025", "JUNO reactor oscillation 2025"],
    ['t:"neutrinoless double beta decay" since 2022', "neutrinoless double beta decay"],
    ["T2K oscillation last 2 years", "T2K oscillation"],
    ["NOvA T2K joint analysis", "NOvA T2K joint analysis"],
    ["KATRIN neutrino mass", "KATRIN neutrino mass"],
    ["neutrino mass ordering global fit last 3 years", "mass ordering, global fits"],
    ["sterile neutrino gallium anomaly", "gallium anomaly"],
    ["IceCube DeepCore atmospheric oscillations", "IceCube DeepCore oscillations"],
    ["coherent elastic neutrino-nucleus scattering", "CEvNS"],
    ["leptogenesis seesaw review", "leptogenesis and seesaw"],
    ["DUNE CP violation sensitivity", "DUNE CP sensitivity"],
    ["Super-Kamiokande solar neutrinos", "Super-K solar neutrinos"],
    ["cosmological bound on neutrino mass DESI", "cosmology and Σmν"],
    ["KM3NeT ORCA mass ordering", "KM3NeT/ORCA"],
    ["modular symmetry lepton flavour", "modular flavour symmetry"],
    ["non-standard neutrino interactions oscillations", "NSI in oscillations"],
    ["2503.07752", "an arXiv number"]
  ];
  (function () {
    var box = document.getElementById("lit-try");
    if (!box) return;
    var pool = EXAMPLES.slice(), pick = [];
    while (pick.length < 4 && pool.length) pick.push(pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
    elFree.setAttribute("placeholder", "e.g. " + pick[0][0]);
    box.textContent = "Try: ";
    pick.slice(1).forEach(function (ex, i) {
      if (i) box.appendChild(document.createTextNode(" · "));
      var a = document.createElement("a");
      a.href = "#";
      a.setAttribute("data-example", ex[0]);
      a.textContent = ex[1];
      box.appendChild(a);
    });
  })();
  Array.prototype.forEach.call(document.querySelectorAll("[data-example]"), function (b) {
    b.addEventListener("click", function (e) {
      e.preventDefault();
      elFree.value = b.getAttribute("data-example");
      userTouched = {};
      applyParse();
      run();
    });
  });

  // A hook for tools/search_live_check.js, which needs the entity table; it
  // does nothing unless that script asks for it.
  if (typeof window.__LIT_EXPOSE__ === "function") {
    window.__LIT_EXPOSE__({ ENTITIES: ENTITIES, ENTITY_RE: ENTITY_RE,
                            gateTerms: gateTerms, stemOf: stemOf,
                            normTitle: normTitle,
                            rows: function () { return state.rows; },
                            pending: function () { return state.pending; },
                            failures: function () { return state.failures; } });
  }

  // Prefill from ?q= so searches can be linked to.
  // The sort bar exists before the first search — see renderControls — so it
  // has to be drawn once at start-up too, not only when an answer arrives.
  renderControls();

  var qs = new URLSearchParams(location.search).get("q");
  if (qs) { elFree.value = qs; applyParse(); run(); }
  else renderChips(null);
})();
