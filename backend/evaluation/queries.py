"""Proposed, human-reviewable information needs; these are never relevance labels."""
TOPICS = [
 ('computer_science','exact','graph neural networks','Find graph neural network architectures, learning methods, or substantive applications.'),
 ('computer_science','natural_language','methods for detecting cancer using medical images','Find computational methods that detect or classify cancer from medical imaging data.'),
 ('computer_science','vocabulary_mismatch','finding unusual behavior in computer networks','Find network intrusion or anomaly detection methods and evaluations.'),
 ('computer_science','narrow','retrieval augmented language models for question answering','Find systems that retrieve external evidence to improve language model question answering.'),
 ('computer_science','technical','differential privacy in federated learning','Find methods and analyses combining federated learning with differential privacy guarantees.'),
 ('computer_science','exact','formal verification of distributed systems','Find formal methods for proving correctness of distributed protocols or systems.'),
 ('mathematics','exact','spectral graph theory','Find research on graph spectra and their combinatorial or structural implications.'),
 ('mathematics','technical','optimal transport on Riemannian manifolds','Find mathematical results concerning optimal transport in Riemannian geometry.'),
 ('mathematics','natural_language','solutions of nonlinear partial differential equations','Find existence, uniqueness, or regularity results for nonlinear partial differential equations.'),
 ('mathematics','narrow','prime gaps and analytic number theory','Find analytic number theoretic results on spacing between primes.'),
 ('physics','technical','quantum entanglement entropy in black holes','Find studies of entanglement entropy related to black hole physics.'),
 ('physics','exact','gravitational wave parameter estimation','Find methods for estimating source parameters from gravitational wave observations.'),
 ('physics','natural_language','how galaxies form and evolve','Find theoretical, computational, or observational research on galaxy formation and evolution.'),
 ('physics','narrow','topological superconductivity in Majorana systems','Find research connecting Majorana modes with topological superconductivity.'),
 ('physics','technical','dark matter direct detection','Find experiments or theory about direct detection of dark matter particles.'),
 ('statistics','exact','Bayesian hierarchical models','Find methods, theory, or substantive applications of hierarchical Bayesian models.'),
 ('statistics','vocabulary_mismatch','estimating cause and effect from observational data','Find causal inference methods for observational datasets.'),
 ('statistics','technical','uncertainty quantification for deep learning','Find methods measuring predictive uncertainty in deep learning models.'),
 ('statistics','narrow','change point detection in multivariate time series','Find methods locating distributional changes in multivariate temporal data.'),
 ('quantitative_biology','narrow','transformer architectures for protein sequence representation','Find transformer methods learning useful representations of protein sequences.'),
 ('quantitative_biology','exact','gene regulatory network inference','Find methods inferring interactions between genes from biological measurements.'),
 ('quantitative_biology','natural_language','modeling spread of infectious diseases','Find mathematical or computational models for infectious disease transmission.'),
 ('electrical_engineering','technical','massive MIMO channel estimation','Find methods and analyses for channel estimation in massive MIMO communication.'),
 ('electrical_engineering','exact','compressed sensing signal reconstruction','Find sparse recovery methods for reconstructing signals from undersampled measurements.'),
 ('electrical_engineering','narrow','model predictive control for autonomous vehicles','Find model predictive control methods for autonomous vehicle motion or trajectory planning.'),
 ('economics','natural_language','effects of economic policy on income inequality','Find analyses of how policy changes affect income distribution or inequality.'),
 ('economics','technical','mechanism design and auctions','Find theory or applications of mechanism design for auctions.'),
 ('quantitative_finance','vocabulary_mismatch','algorithms for identifying unusual financial transactions','Find computational anomaly or fraud detection methods for financial transactions.'),
 ('quantitative_finance','technical','portfolio optimization under transaction costs','Find portfolio allocation methods accounting for trading costs.'),
 ('cross_disciplinary','cross_disciplinary','machine learning approaches for climate prediction','Find machine learning methods for forecasting climate variables or climate dynamics.'),
]


def defaults():
    return [dict(id=f'Q{i:03}', query=q, information_need=need, domain=domain, query_type=kind,
                 notes='Proposed default information need; review before finalizing experiments.')
            for i, (domain, kind, q, need) in enumerate(TOPICS, 1)]
