# Code of Conduct

This is a short document because it has one rule that matters more than the
rest, and burying it in a long list would defeat the point.

## The rule that is specific to this project

**Do not ask anyone to identify themselves, to name their country or city, or to
describe the network or the radio conditions they are working under.**

Not in an issue, not in a pull request review, not in a discussion thread, not
in a private message. This applies to users and to contributors, and it applies
to the maintainer as much as to anyone else.

JavidNet is a network made of people who can be found: a dish on a roof, a wire
antenna, a person who vouched for another person. A question like "where are you
testing this?" or "can you send the log from your node?" is asked without
thinking and is very hard to refuse. Refusing looks evasive. Answering can put
somebody in a room with the police. So the burden sits on the person asking, not
on the person answering.

In practice:

- Do not ask for a location, a grid square, an operator, an IP address, a
  callsign, a node id, a public key, or a QR code from a real deployment.
- Do not ask whether someone owns a dish or a transceiver.
- Do not ask for a node log, a peer list, a `trust.db` extract, a beacon
  capture, or a route table from a live network. Those carry the same
  information in a form that looks technical.
- Ask for the code path or the diagram, not the deployment. Nearly every bug in
  this repository reproduces from two nodes on one laptop.
- If someone volunteers their location or their setup, do not repeat it, quote
  it, or build on it in a later thread.
- Do not work out who someone is from a timezone, a commit time, a language, or
  a photograph, and never say so if you have.
- Do not ask a contributor to transmit on HF to prove something. Transmitting is
  the moment of exposure. Nothing in a code review is worth that.

Breaking this rule is treated as a serious matter even when there was no bad
intent, because the harm does not depend on intent.

## A note on the HF radio material

The gateway tables in `hf-radio-diagrams/` are drawn from the public Winlink
gateway list, and the callsigns shown there are examples. Do not add a real
individual's callsign, home location, or operating schedule to this repository,
even if you found it in a public directory. A public record and a curated list
in a censorship-circumvention repository are not the same object.

## The ordinary rules

- Be direct about the design and considerate about people. Blunt technical
  criticism is fine. Contempt is not.
- No harassment, insults, or personal attacks. No sexual attention. No
  discrimination on any ground.
- Assume the person you are talking to is not writing in their first language.
  Ask what they meant before you decide they were rude.
- Stay on the topic the thread is about. This project touches politics by its
  nature. Arguing politics in a pull request does not.
- Do not use this repository to organise anything, or to speak for anyone other
  than yourself.

## Scope

This applies in the repository, in issues and pull requests, in discussions, and
anywhere someone is representing the project.

## Reporting

Report a problem privately, through the contact route on the project's GitHub
page, or through GitHub private vulnerability reporting if the matter also
involves a security issue.

Say what happened and where. You do not need to identify yourself to the
maintainer, and you will not be asked to.

## What happens then

One maintainer handles this, so the response is proportionate and quick rather
than formal. In order of severity: a comment is edited or removed, a private
warning is sent, and an account is blocked from the repository.

A comment that carries someone's identifying information is removed on sight,
before any discussion about who was at fault. Removing the information comes
first.
