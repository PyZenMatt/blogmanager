---
canonical: 
categories:
  - test_cat
date: 2025-08-21 09\:11\:00
description: Feature\: Integrità slug multi sito Scenario\: Generazione automatica con collisione nello stesso sito Given un sito "site a" When creo due post con lo stesso ti…
layout: post
slug: feature-integrita-slug-multi
tags:
title: Feature\: Integrità slug multi-sito
---

Feature: Integrità slug multi-sito
  Scenario: Generazione automatica con collisione nello stesso sito
    Given un sito "site-a"
    When creo due post con lo stesso titolo senza slug
    Then entrambi sono 201
    And il secondo ha slug con suffisso "-2"

  Scenario: Slug uguale su siti diversi
    Given due siti "site-a" e "site-b"
    When creo un post con slug "same" su entrambi
    Then entrambi sono 201

  Scenario: Conflitto esplicito
    Given un sito "site-a"
    And esiste un post con slug "dup"
    When creo un secondo post con slug "dup"
    Then la risposta è 409
    And il body spiega il conflitto di slug per quel sito
