"""Future Devin checker adapter contract."""

from fcgc.checking.compliance_checker import CanonicalChecker, unresolved


class DevinChecker(CanonicalChecker):
    provider = "devin"
    model = "unimplemented"

    def predict(self, task, prompt):
        return (
            unresolved(task, "Devin adapter contract is unimplemented; no API assumed."),
            None,
            None,
            None,
        )
