theorem Entry.answer : Golf.WindowLogic :=
  fun _ _ _ _ _ supply oscillation disjoint hz =>
    (oscillation hz).elim fun k bad =>
      (supply k).elim fun y good => disjoint y good.2 (bad y good.1)
