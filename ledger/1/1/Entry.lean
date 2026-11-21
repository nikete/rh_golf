theorem Entry.answer : Golf.Reflection := by
  intro right s hz nontrivial hs1
  have hs0 : s ≠ 0 := by
    rintro rfl
    exact (div_ne_zero (neg_ne_zero.mpr one_ne_zero) two_ne_zero)
      (riemannZeta_zero.symm.trans hz)
  have hGamma : Complex.Gammaℝ s ≠ 0 := by
    intro h
    obtain ⟨n, hn⟩ := Complex.Gammaℝ_eq_zero_iff.mp h
    cases n with
    | zero => exact hs0 (by simpa only [Nat.cast_zero, mul_zero, neg_zero] using hn)
    | succ n => exact nontrivial ⟨n, by simpa only [Nat.cast_succ, neg_mul] using hn⟩
  have hc : completedRiemannZeta s = 0 :=
    (div_eq_zero_iff.mp ((riemannZeta_def_of_ne_zero hs0).symm.trans hz)).resolve_right hGamma
  rcases lt_trichotomy s.re (1 / 2) with h | h | h
  · have hr : (1 / 2 : ℝ) < (1 - s).re := calc
      1 / 2 = 1 - 1 / 2 := (sub_half (1 : ℝ)).symm
      _ < 1 - s.re := sub_lt_sub_left h 1
    exact (right (1 - s) hr (fun e => hs0 (sub_eq_self.mp e))
      ((riemannZeta_def_of_ne_zero (sub_ne_zero.mpr hs1.symm)).trans
        (div_eq_zero_iff.mpr (.inl ((completedRiemannZeta_one_sub s).trans hc))))).elim
  · exact h
  · exact (right s h hs1 hz).elim
