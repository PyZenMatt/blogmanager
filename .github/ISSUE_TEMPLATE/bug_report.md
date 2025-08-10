name: "Bug report"
description: "Segnala un malfunzionamento"
title: "Bug: <breve>"
labels: ["type: bug", "priority: P1"]
body:
  - type: textarea
    id: context
    attributes:
      label: Contesto
      description: Atteso vs osservato
  - type: textarea
    id: repro
    attributes:
      label: Repro
      description: "1) … 2) …"
  - type: textarea
    id: evidence
    attributes:
      label: Evidenze
      description: Log/screenshot
  - type: textarea
    id: acceptance
    attributes:
      label: Accettazione (Gherkin)
      description: Given/When/Then
