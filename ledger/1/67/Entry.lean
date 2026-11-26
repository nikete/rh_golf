-- archive-module: Development.AutomorphicSpectrum.Proofs.AlgebraProofs.PureFamilyDecompositionStatement
open NumberField GlobalTheory CompanionTheory Ar Fl Submodule Set PureType Function Nat Sum
attribute [grind] nsmul_mem sgnRt add_mem_cancel_left add_mem_cancel_right cast_eq_zero disjoint_def mem_sup comp_def mem_span range_eq span_union
grind_pattern disjoint_lat => lat hP ρ, -ρ'
set_option hygiene false
notation "𝒮" f => multiplesHom _ y n ∈ span (𝓞 E) (range $ x ∘ f)
set_option maxHeartbeats 4000000 in
theorem Entry.answer E [Field E] [NumberField E] [IsCMField E] H D g ty P hP p q x n :
    @IsPure E _ _ _ H D g ty P hP p q x →
    dsimp% let L := lat hP ∘ sgnRt H
    (∀ y, 𝒮 id) → (∀ y, ∃ a ∈ L true, ∃ b ∈ L false, n • y = a + b) ∧ (∀ y ∈ L true, 𝒮 inl) ∧ ∀ y ∈ L false, 𝒮 inr := by
  rintro ⟨hxL, hxR⟩ hn
  let L := lat hP (sgnRt H true)
  let R := lat hP (sgnRt H false)
  let A := span (𝓞 E) (range (x ∘ inl))
  let B := span (𝓞 E) (range (x ∘ inr))
  have hA : A ≤ L := span_le.mpr (by rintro _ ⟨i, rfl⟩; exact hxL i)
  have hB : B ≤ R := span_le.mpr (by rintro _ ⟨i, rfl⟩; exact hxR i)
  have split (y : D.La) : ∃ a ∈ A, ∃ b ∈ B, a + b = n • y := by
    have hh := hn y
    change n • y ∈ span (𝓞 E) (range x) at hh
    rw [range_eq x, span_union, mem_sup] at hh
    exact hh
  have hdis : Disjoint L R := by
    apply disjoint_lat
    change H.rt0 ≠ -H.rt0
    intro e
    have hzero : H.rt0 = 0 := by linear_combination (1 / 2 : ℂ) * e
    have hs := H.sqrt_neg_disc_sq
    simp [hzero] at hs
    exact H.d_prime.ne_zero (by first | exact hs | exact hs.symm)
  refine ⟨?_, ?_, ?_⟩
  · intro y
    obtain ⟨a, ha, b, hb, hab⟩ := split y
    exact ⟨a, hA ha, b, hB hb, hab.symm⟩
  · intro y hy
    obtain ⟨a, ha, b, hb, hab⟩ := split y
    have hsum : a + b ∈ L := hab ▸ L.nsmul_mem hy n
    have hzero := Submodule.disjoint_def.mp hdis b ((add_mem_cancel_left (hA ha)).mp hsum) (hB hb)
    change n • y ∈ A
    rw [← hab, hzero, add_zero]
    exact ha
  · intro y hy
    obtain ⟨a, ha, b, hb, hab⟩ := split y
    have hsum : a + b ∈ R := hab ▸ R.nsmul_mem hy n
    have hzero := Submodule.disjoint_def.mp hdis a (hA ha) ((add_mem_cancel_right (hB hb)).mp hsum)
    change n • y ∈ B
    rw [← hab, hzero, zero_add]
    exact hb
