-- archive-module: Formalism.SharpRestriction.LevelLetterCocycles.RepresentationCongruences.SmulEqZeroOfAevalProd
open Polynomial
theorem Entry.answer {O : Type*} [CommRing O] [IsDomain O] (c : ℤ → O) :
    ∀ (s : Finset ℤ), Set.InjOn c (↑s : Set ℤ) → ∀ Q : O[X], (∀ k ∈ s, Q.eval (c k) = 0) →
      (∏ k ∈ s, (X - C (c k))) ∣ Q := by
  intro s hc Q hQ
  obtain rfl | hne := eq_or_ne Q 0
  · exact dvd_zero _
  have hroots : s.val.map c ≤ Q.roots := by
    refine (Multiset.le_iff_subset (s.nodup.map_on fun _ hx _ hy => hc hx hy)).2 ?_
    intro x hx
    obtain ⟨k, hk, rfl⟩ := Multiset.mem_map.mp hx
    exact (Polynomial.mem_roots hne).2 (hQ k hk)
  simpa only [Finset.prod, Multiset.map_map, Function.comp_def] using
    (Multiset.prod_X_sub_C_dvd_iff_le_roots hne (s.val.map c)).2 hroots
