//! Root crate of the workspace.

pub struct RootService {
    pub name: String,
}

impl RootService {
    pub fn new(name: String) -> Self {
        Self { name }
    }
}
