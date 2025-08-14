name: "Feature request"
description: "Proponi una nuova funzionalità"
title: "Feature: <valore>"
labels: ["type: feature", "priority: P2"]
body:
  - type: textarea
    id: story
    attributes:
      label: User Story
      description: "Come <ruolo> voglio <azione> così da <beneficio>"
  - type: textarea
    id: metrics
    attributes:
      label: Metriche/Impatto
  - type: textarea
    id: acceptance
    attributes:
      label: Accettazione (Gherkin)
      description: Given/When/Then
  - type: textarea
    id: notes
    attributes:
      label: Note UX/Tech
