//! First workspace member.

pub trait Greeter {
    fn greet(&self) -> String;
}

pub struct AlphaGreeter;

impl Greeter for AlphaGreeter {
    fn greet(&self) -> String {
        "alpha".to_string()
    }
}
