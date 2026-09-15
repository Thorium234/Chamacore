"""RegistrationFee service."""

import uuid

from sqlalchemy.orm import Session

from app.core.errors import StateError
from app.models.enums import RegistrationFeeStatus, RoleName
from app.models.registration_fee import RegistrationFee
from app.models.user import User
from app.repositories.registration_fee import RegistrationFeeRepository
from app.services.access import (
    authorize_chama_access,
    get_chama_or_404,
    get_target_membership,
    require_role,
)


class RegistrationFeeService:
    def __init__(self, db: Session):
        self.db = db
        self.fees = RegistrationFeeRepository(db)

    def get_for_membership(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> RegistrationFee:
        chama = get_chama_or_404(self.db, chama_id)
        authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        return fee

    def waive(
        self, *, actor: User, chama_id: uuid.UUID, membership_id: uuid.UUID
    ) -> RegistrationFee:
        chama = get_chama_or_404(self.db, chama_id)
        actor_membership = authorize_chama_access(self.db, actor=actor, chama_id=chama.id)
        require_role(actor_membership, RoleName.CHAIRPERSON)
        membership = get_target_membership(self.db, chama_id=chama.id, membership_id=membership_id)
        fee = self.fees.get_by_membership(membership.id)
        if fee is None:
            raise StateError("This membership has no registration fee record")
        if fee.status == RegistrationFeeStatus.WAIVED:
            raise StateError("This registration fee is already waived")
        fee.status = RegistrationFeeStatus.WAIVED
        self.db.commit()
        return fee