open Complex

theorem Entry.answer (hz : ∀ s : ℂ, 1 / 2 < s.re → s ≠ 1 → riemannZeta s ≠ 0) : RiemannHypothesis := by
  intro s hs htriv hs1
  rcases lt_trichotomy s.re (1 / 2) with hlt | heq | hgt
  · exfalso
    have hs0 : s ≠ 0 := by rintro rfl; rw [riemannZeta_zero] at hs; norm_num at hs
    have hG : Gammaℝ s ≠ 0 := fun hg => by
      obtain ⟨n, hn⟩ := Gammaℝ_eq_zero_iff.mp hg
      rcases n with _ | n
      · exact hs0 (by simpa using hn)
      · exact htriv ⟨n, by rw [hn]; push_cast; ring⟩
    have hc : completedRiemannZeta s = 0 :=
      (div_eq_zero_iff.mp (riemannZeta_def_of_ne_zero hs0 ▸ hs)).resolve_right hG
    have h1 : (1 - s) ≠ 1 := fun e => hs0 (by linear_combination -e)
    refine hz (1 - s) (by simp; linarith) h1 ?_
    rw [riemannZeta_def_of_ne_zero (sub_ne_zero.mpr hs1.symm), completedRiemannZeta_one_sub, hc, zero_div]
  · exact heq
  · exact absurd hs (hz s hgt hs1)
