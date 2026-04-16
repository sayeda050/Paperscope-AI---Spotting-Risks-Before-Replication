try:
    from sklearn.linear_model import LogisticRegression as _LogisticRegression

    def _paperscope_get_multi_class(self):
        return self.__dict__.get(
            "multi_class",
            "ovr" if getattr(self, "solver", None) == "liblinear" else "auto",
        )

    def _paperscope_set_multi_class(self, value):
        self.__dict__["multi_class"] = value

    _LogisticRegression.multi_class = property(
        _paperscope_get_multi_class,
        _paperscope_set_multi_class,
    )
except Exception:
    pass