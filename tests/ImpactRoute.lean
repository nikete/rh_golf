import League.Course
import League.Footprint

-- The two typed inputs below model already checked entries in this test environment.
namespace RouteTest
private axiom criterion : Golf.PrimeWindow
private axiom supply : Golf.Windows
private theorem joined : RiemannHypothesis := criterion supply

open Lean Elab Command in
run_cmd do
  let env ← getEnv
  let joinedName := ``joined
  let names := (∅ : NameSet).insert joinedName
  let .ok fp := Golf.Footprint.measure env names joinedName | throwError "could not measure the application"
  unless fp == Json.mkObj [("version", toJson 1), ("private_nodes", toJson 4),
                          ("shared", Json.mkObj [])] do
    throwError "unexpected composition footprint {fp.compress}"
end RouteTest
