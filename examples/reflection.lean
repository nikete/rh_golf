theorem Entry.answer : Golf.Reflection := by
  intro right s hz nontrivial hs1
  have hs0 : s ≠ 0 := by
    rintro rfl
    rw [riemannZeta_zero] at hz
    norm_num at hz
  have hGamma : Complex.Gammaℝ s ≠ 0 := by
    intro h
    obtain ⟨n, hn⟩ := Complex.Gammaℝ_eq_zero_iff.mp h
    cases n with
    | zero => exact hs0 (by simpa using hn)
    | succ n => exact nontrivial ⟨n, by simpa [neg_mul] using hn⟩
  have hcompleted : completedRiemannZeta s = 0 := by
    rw [riemannZeta_def_of_ne_zero hs0] at hz
    exact (div_eq_zero_iff.mp hz).resolve_right hGamma
  rcases lt_trichotomy s.re (1 / 2) with h | h | h
  · exfalso
    apply right (1 - s) (by rw [Complex.sub_re, Complex.one_re]; linarith)
      (by intro he; exact hs0 (sub_eq_self.mp he))
    rw [riemannZeta_def_of_ne_zero (sub_ne_zero.mpr hs1.symm),
      completedRiemannZeta_one_sub, hcompleted, zero_div]
  · exact h
  · exact (right s h hs1 hz).elim
