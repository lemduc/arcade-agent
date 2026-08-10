//! Second workspace member, depending on the first.

use alpha::AlphaGreeter;

pub struct BetaClient {
    greeter: AlphaGreeter,
}
