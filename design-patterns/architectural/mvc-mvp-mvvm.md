---
slug: mvc-mvp-mvvm
name: MVC / MVP / MVVM
category: architectural
intent: Separate UI presentation from business logic via Model + View + Controller/Presenter/ViewModel
references: Trygve Reenskaug; Fowler PEAA
---

# When to use
Any non-trivial UI app: web, mobile, desktop.  Picking the variant depends on the framework:
- MVC: server-rendered HTML (ASP.NET MVC, Rails)
- MVVM: data-binding-heavy frameworks (WPF, modern XAML, Vue/Angular)
- MVP: classic Android, plain WinForms

The View is dumb (renders), the Model is the domain, the middle thing (Controller/Presenter/ViewModel) wires user input to model changes.

# When NOT to use
A single-screen tool — the layering is overhead.

The 'controller' has become a god-class — split into multiple controllers/presenters by use case.

You're using React or modern reactive UIs where the model is reactive state (Redux store, signals) and 'controller' is just event handlers — the labels stop helping; embrace your framework's idioms.

# Structure
Model = data + business rules.  View = rendering.  Controller/Presenter/ViewModel = the glue: takes user input, calls Model, presents Model state to the View.

# Example
```typescript
// Modern MVVM-ish React with TanStack Query — the 'ViewModel' is the hook
function useFleetCockpit(fleetId: FleetId) {
  const { data: fleet } = useQuery({ queryKey: ['fleet', fleetId], queryFn: () => api.getFleet(fleetId) });
  const issue = useMutation({ mutationFn: (cmd: FleetCommand) => api.issueFleetCommand(fleetId, cmd) });
  return { fleet, issue };
}
function FleetCockpitPage() {
  const { fleet, issue } = useFleetCockpit(fleetId);  // ViewModel
  return <FleetMap fleet={fleet} onFormUp={() => issue.mutate({ verb: 'form-up' })} />;
}
```

# Relationships
Foundation of UI architecture.  Pairs with reactive-state-management (Redux, MobX, signals).  Foundation under the Acme web SPA.
