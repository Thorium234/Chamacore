# Domain Model

## User

A person who can authenticate. A User may be linked to a Member.

## Chama

A savings or investment group managed by ChamaCore.

## Member

The identity of a person. A Member is not inherently tied to one Chama.

## Membership

The relationship between one Member and one Chama. Chama-specific financial
records reference Membership, not Member.

## Role

A permission role within a Chama:

- `CHAIRPERSON`
- `TREASURER`
- `SECRETARY`
- `MEMBER`

## MembershipRole

Associates a Role with a Membership.

## RegistrationFee

Represents the registration-fee obligation or record for a Membership.

## Contribution

Represents money recorded against a Membership for a defined contribution
period.

## Share

Represents units created according to the approved share formula.

## Relationships

```text
User
  ↓ optional link
Member
  ↓
Membership
  ↓
Chama

Membership
  ├── MembershipRole
  ├── RegistrationFee
  ├── Contribution
  └── Share
```

## Identity rule

Member means the person. Membership means that person's relationship with one
Chama. A Member may have memberships in multiple Chamas.