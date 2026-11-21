theorem Entry.answer : Golf.WindowLogic := by
  intro I later zero good bad supply oscillation disjoint hz
  obtain ⟨k, hk⟩ := oscillation hz
  obtain ⟨y, hy, hg⟩ := supply k
  exact disjoint y hg (hk y hy)
